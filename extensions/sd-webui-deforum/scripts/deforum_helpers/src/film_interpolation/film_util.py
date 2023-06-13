"""Various utilities used in the film_net frame interpolator model."""
from typing import List, Optional

import cv2
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F


def pad_batch(batch, align):
    height, width = batch.shape[1:3]
    height_to_pad = (align - height % align) if height % align != 0 else 0
    width_to_pad = (align - width % align) if width % align != 0 else 0

    crop_region = [height_to_pad >> 1, width_to_pad >> 1, height + (height_to_pad >> 1), width + (width_to_pad >> 1)]
    batch = np.pad(batch, ((0, 0), (height_to_pad >> 1, height_to_pad - (height_to_pad >> 1)),
                           (width_to_pad >> 1, width_to_pad - (width_to_pad >> 1)), (0, 0)), mode='constant')
    return batch, crop_region


def load_image(path, align=64):
    image = cv2.cvtColor(cv2.imread(path), cv2.COLOR_BGR2RGB).astype(np.float32) / np.float32(255)
    image_batch, crop_region = pad_batch(np.expand_dims(image, axis=0), align)
    return image_batch, crop_region


def build_image_pyramid(image: torch.Tensor, pyramid_levels: int = 3) -> List[torch.Tensor]:
    """Builds an image pyramid from a given image.

    The original image is included in the pyramid and the rest are generated by
    successively halving the resolution.

    Args:
      image: the input image.
      options: film_net options object

    Returns:
      A list of images starting from the finest with options.pyramid_levels items
    """

    pyramid = []
    for i in range(pyramid_levels):
        pyramid.append(image)
        if i < pyramid_levels - 1:
            image = F.avg_pool2d(image, 2, 2)
    return pyramid


def warp(image: torch.Tensor, flow: torch.Tensor) -> torch.Tensor:
    """Backward warps the image using the given flow.

    Specifically, the output pixel in batch b, at position x, y will be computed
    as follows:
      (flowed_y, flowed_x) = (y+flow[b, y, x, 1], x+flow[b, y, x, 0])
      output[b, y, x] = bilinear_lookup(image, b, flowed_y, flowed_x)

    Note that the flow vectors are expected as [x, y], e.g. x in position 0 and
    y in position 1.

    Args:
      image: An image with shape BxHxWxC.
      flow: A flow with shape BxHxWx2, with the two channels denoting the relative
        offset in order: (dx, dy).
    Returns:
      A warped image.
    """
    flow = -flow.flip(1)

    dtype = flow.dtype
    device = flow.device

    # warped = tfa_image.dense_image_warp(image, flow)
    # Same as above but with pytorch
    ls1 = 1 - 1 / flow.shape[3]
    ls2 = 1 - 1 / flow.shape[2]

    normalized_flow2 = flow.permute(0, 2, 3, 1) / torch.tensor(
        [flow.shape[2] * .5, flow.shape[3] * .5], dtype=dtype, device=device)[None, None, None]
    normalized_flow2 = torch.stack([
        torch.linspace(-ls1, ls1, flow.shape[3], dtype=dtype, device=device)[None, None, :] - normalized_flow2[..., 1],
        torch.linspace(-ls2, ls2, flow.shape[2], dtype=dtype, device=device)[None, :, None] - normalized_flow2[..., 0],
    ], dim=3)

    warped = F.grid_sample(image, normalized_flow2,
                           mode='bilinear', padding_mode='border', align_corners=False)
    return warped.reshape(image.shape)


def multiply_pyramid(pyramid: List[torch.Tensor],
                     scalar: torch.Tensor) -> List[torch.Tensor]:
    """Multiplies all image batches in the pyramid by a batch of scalars.

    Args:
      pyramid: Pyramid of image batches.
      scalar: Batch of scalars.

    Returns:
      An image pyramid with all images multiplied by the scalar.
    """
    # To multiply each image with its corresponding scalar, we first transpose
    # the batch of images from BxHxWxC-format to CxHxWxB. This can then be
    # multiplied with a batch of scalars, then we transpose back to the standard
    # BxHxWxC form.
    return [image * scalar for image in pyramid]


def flow_pyramid_synthesis(
        residual_pyramid: List[torch.Tensor]) -> List[torch.Tensor]:
    """Converts a residual flow pyramid into a flow pyramid."""
    flow = residual_pyramid[-1]
    flow_pyramid: List[torch.Tensor] = [flow]
    for residual_flow in residual_pyramid[:-1][::-1]:
        level_size = residual_flow.shape[2:4]
        flow = F.interpolate(2 * flow, size=level_size, mode='bilinear')
        flow = residual_flow + flow
        flow_pyramid.insert(0, flow)
    return flow_pyramid


def pyramid_warp(feature_pyramid: List[torch.Tensor],
                 flow_pyramid: List[torch.Tensor]) -> List[torch.Tensor]:
    """Warps the feature pyramid using the flow pyramid.

    Args:
      feature_pyramid: feature pyramid starting from the finest level.
      flow_pyramid: flow fields, starting from the finest level.

    Returns:
      Reverse warped feature pyramid.
    """
    warped_feature_pyramid = []
    for features, flow in zip(feature_pyramid, flow_pyramid):
        warped_feature_pyramid.append(warp(features, flow))
    return warped_feature_pyramid


def concatenate_pyramids(pyramid1: List[torch.Tensor],
                         pyramid2: List[torch.Tensor]) -> List[torch.Tensor]:
    """Concatenates each pyramid level together in the channel dimension."""
    result = []
    for features1, features2 in zip(pyramid1, pyramid2):
        result.append(torch.cat([features1, features2], dim=1))
    return result


def conv(in_channels, out_channels, size, activation: Optional[str] = 'relu'):
    # Since PyTorch doesn't have an in-built activation in Conv2d, we use a
    # Sequential layer to combine Conv2d and Leaky ReLU in one module.
    _conv = nn.Conv2d(
        in_channels=in_channels,
        out_channels=out_channels,
        kernel_size=size,
        padding='same')
    if activation is None:
        return _conv
    assert activation == 'relu'
    return nn.Sequential(
        _conv,
        nn.LeakyReLU(.2)
    )