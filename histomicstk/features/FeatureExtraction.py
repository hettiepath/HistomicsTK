from .ComputeFSDs import ComputeFSDs
from .ComputeTextureFeatures import ComputeTextureFeatures
from .ComputeGradientFeatures import ComputeGradientFeatures
from .ComputeIntensityFeatures import ComputeIntensityFeatures
import numpy as np
import pandas as pd
from skimage.feature import canny
from skimage.measure import regionprops
from skimage.morphology import disk, dilation

def FeatureExtraction(Label, In, Ic, K=128, Fs=6, Delta=8):
    """
    Calculates features from a label image.

    Parameters
    ----------
    Label : array_like
        A M x N label image.
    In : array_like
        A M x N intensity image for Nuclei.
    Ic : array_like
        A M x N intensity image for Cytoplasms.
    K : Number of points for boundary resampling to calculate fourier
        descriptors. Default value = 128.
    Fs : Number of frequency bins for calculating FSDs. Default value = 6.
    Delta : scalar, used to dilate nuclei and define cytoplasm region.
            Default value = 8.
    Returns
    -------
    df : 2-dimensional labeled data structure, float64
        Pandas data frame.
    Notes
    -----
    The following features are computed:

    - `Centroids`:
        - X,Y

    - `Morphometry features`:
        - Area,
        - Perimeter,
        - MajorAxisLength,
        - MinorAxisLength,
        - Eccentricity,
        - Circularity,
        - Extent,
        - Solidity

    - `Fourier shape descriptors`:
        - FSD1-FSD6

    - Intensity features for hematoxylin and cytoplasm channels:
        - MinIntensity, MaxIntensity,
        - MeanIntensity, StdIntensity,
        - MeanMedianDifferenceIntensity,
        - Entropy, Energy, Skewness and Kurtosis

    - Gradient/edge features for hematoxylin and cytoplasm channels:
        - MeanGradMag, StdGradMag, SkewnessGradMag, KurtosisGradMag,
        - EntropyGradMag, EnergyGradMag,
        - SumCanny, MeanCanny

    References
    ----------
    .. [1] D. Zhang et al. "A comparative study on shape retrieval using
       Fourier descriptors with different shape signatures," In Proc.
       ICIMADE01, 2001.
    .. [2] Daniel Zwillinger and Stephen Kokoska. "CRC standard probability
       and statistics tables and formulae," Crc Press, 1999.
    """

    # get Label size x
    size_x = Label.shape[0]
    size_y = Label.shape[1]

    # get the number of objects in Label
    regions = regionprops(Label)
    num = len(regions)

    # initialize centroids
    CentroidX = np.zeros(num)
    CentroidY = np.zeros(num)

    # initialize morphometry features
    Area = np.zeros(num)
    Perimeter = np.zeros(num)
    Eccentricity = np.zeros(num)
    Circularity = np.zeros(num)
    MajorAxisLength = np.zeros(num)
    MinorAxisLength = np.zeros(num)
    Extent = np.zeros(num)
    Solidity = np.zeros(num)

    # initialize FSD feature group
    FSDGroup = np.zeros((num, Fs))

    # initialize texture feature groups
    HematoxylinTextureGroup = np.zeros((num, 4))
    EosinTextureGroup = np.zeros((num, 4))

    # initialize gradient feature groups
    HematoxylinGradientGroup = np.zeros((num, 8))
    EosinGradientGroup = np.zeros((num, 8))

    # initialize intensity feature groups
    HematoxylinIntensityGroup = np.zeros((num, 5))
    EosinIntensityGroup = np.zeros((num, 5))

    # create round structuring element
    Disk = disk(Delta)

    # compute bw canny and gradient difference for H and E
    Gnx, Gny = np.gradient(In)
    diffGn = np.sqrt(Gnx**2 + Gny**2)
    BW_cannyn = canny(In)

    Gcx, Gcy = np.gradient(Ic)
    diffGc = np.sqrt(Gcx**2 + Gcy**2)
    BW_cannyc = canny(Ic)

    # set region index
    regionIdx = 0

    # do feature extraction
    for i in range(0, num):
        # compute Centroids
        CentroidX[i] = regions[i].centroid[0]
        CentroidY[i] = regions[i].centroid[1]
        # compute Area
        Area[i] = regions[i].area
        # compute Perimeter
        Perimeter[i] = regions[i].perimeter
        # compute Eccentricity
        Eccentricity[i] = regions[i].eccentricity
        # compute Circularity
        numerator = 4 * np.pi * Area[i]
        denominator = np.power(Perimeter[i], 2)
        Circularity[i] = numerator / denominator if denominator else 0
        # compute MajorAxisLength and MinorAxisLength
        MajorAxisLength[i] = regions[i].major_axis_length
        MinorAxisLength[i] = regions[i].minor_axis_length
        # compute Extent
        Extent[i] = regions[i].extent
        # compute Solidity
        Solidity[i] = regions[i].solidity
        # get bounds of dilated nucleus
        min_row, max_row, min_col, max_col = \
            GetBounds(regions[i].bbox, Delta, size_x, size_y)
        # grab nucleus mask
        Nucleus = (
            Label[min_row:max_row, min_col:max_col] == regions[i].label
        ).astype(np.bool)
        # compute Fourier shape descriptors
        FSDGroup[regionIdx, :] = ComputeFSDs(Nucleus, K, Fs)
        # generate object coords for nuclei and cytoplasmic regions
        Nuclei = regions[i].coords
        # compute Texture, Gradient, Intensity features
        HematoxylinTextureGroup[regionIdx, :] = \
            ComputeTextureFeatures(In, Nuclei)
        HematoxylinGradientGroup[regionIdx, :] = \
            ComputeGradientFeatures(In, Nuclei, diffGn, BW_cannyn)
        HematoxylinIntensityGroup[regionIdx, :] = \
            ComputeIntensityFeatures(In, Nuclei)
        # get mask for all nuclei in neighborhood
        Mask = (
            Label[min_row:max_row, min_col:max_col] > 0
        ).astype(np.uint8)
        # remove nucleus region from cytoplasm+nucleus mask
        cytoplasm = (
            np.logical_xor(Mask, dilation(Nucleus, Disk))
        )
        # get list of cytoplasm pixels
        regionCoords = np.argwhere(cytoplasm == 1)
        regionCoords[:,0] = regionCoords[:,0] + min_row
        regionCoords[:,1] = regionCoords[:,1] + min_col
        # compute Texture, Gradient, Intensity features
        EosinTextureGroup[regionIdx, :] = \
            ComputeTextureFeatures(Ic, regionCoords)
        EosinGradientGroup[regionIdx, :] = \
            ComputeGradientFeatures(Ic, regionCoords, diffGc, BW_cannyc)
        EosinIntensityGroup[regionIdx, :] = \
            ComputeIntensityFeatures(Ic, regionCoords)
        # increase region index
        regionIdx = regionIdx + 1

    # initialize panda dataframe
    df = pd.DataFrame()

    # add columns to dataframe
    df['X'] = CentroidX
    df['Y'] = CentroidY

    df['Area'] = Area
    df['Perimeter'] = Perimeter
    df['Eccentricity'] = Eccentricity
    df['Circularity'] = Circularity
    df['MajorAxisLength'] = MajorAxisLength
    df['MinorAxisLength'] = MinorAxisLength
    df['Extent'] = Extent
    df['Solidity'] = Solidity

    for i in range(0, Fs):
        df['FSD' + str(i+1)] = FSDGroup[:, i]

    TextureNames = ['Entropy', 'Energy', 'Skewness', 'Kurtosis']

    for i in range(0, len(TextureNames)):
        df['Hematoxylin' + TextureNames[i]] = HematoxylinTextureGroup[:, i]
        df['Cytoplasm' + TextureNames[i]] = EosinTextureGroup[:, i]

    GradientNames = ['MeanGradMag', 'StdGradMag', 'EntropyGradMag',
        'EnergyGradMag', 'SkewnessGradMag', 'KurtosisGradMag', 'SumCanny',
        'MeanCanny']

    for i in range(0, len(GradientNames)):
        df['Hematoxylin' + GradientNames[i]] = HematoxylinGradientGroup[:, i]
        df['Cytoplasm' + GradientNames[i]] = EosinGradientGroup[:, i]

    IntensityNames = ['MeanIntensity', 'MeanMedianDifferenceIntensity', \
        'MaxIntensity', 'MinIntensity', 'StdIntensity']

    for i in range(0, len(IntensityNames)):
        df['Hematoxylin' + IntensityNames[i]] = HematoxylinIntensityGroup[:, i]
        df['Cytoplasm' + IntensityNames[i]] = EosinIntensityGroup[:, i]

    return df


def GetBounds(bbox, delta, M, N):
    """
    Returns bounds of object in global label image.

    Parameters
    ----------
    bbox : tuple
        Bounding box (min_row, min_col, max_row, max_col).
    delta : int
        Used to dilate nuclei and define cytoplasm region.
        Default value = 8.
    M : int
        X size of label image.
    N : int
        Y size of label image.

    Returns
    -------
    min_row : int
        Minum row of the region bounds.
    max_row : int
        Maximum row of the region bounds.
    min_col : int
        Minum column of the region bounds.
    max_col : int
        Maximum column of the region bounds.
    """

    min_row, min_col, max_row, max_col = bbox

    min_row_out = max(0, (min_row - delta))
    max_row_out = min(M-1, (max_row + delta))
    min_col_out = max(0, (min_col - delta))
    max_col_out = min(N-1, (max_col + delta))

    return min_row_out, max_row_out, min_col_out, max_col_out
