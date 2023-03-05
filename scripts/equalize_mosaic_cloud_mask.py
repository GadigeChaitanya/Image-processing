import os
import sys
import logging
import argparse
import rasterio
import numpy as np

from coloredlogs import ColoredFormatter
from osgeo import gdal, osr
from skimage.exposure import match_histograms
from skimage.morphology import dilation, erosion
from skimage.morphology import disk


def array2raster(new_raster, dataset, array, d_type):
    """ Save GTiff file from numpy.array

    :param new_raster: save file name
    :param dataset : original tif file
    :param array : numpy.array
    :param d_type: Byte or Float32
    """
    cols = array.shape[1]
    rows = array.shape[0]
    origin_x, pixel_width, b, origin_y, d, pixel_height = dataset.GetGeoTransform()

    driver = gdal.GetDriverByName('GTiff')

    gdt_d_type = gdal.GDT_Unknown
    if d_type == "Byte":
        gdt_d_type = gdal.GDT_Byte
    elif d_type == "Float32":
        gdt_d_type = gdal.GDT_Float32
    elif d_type == "uint16":
        gdt_d_type = gdal.GDT_UInt16
    else:
        logging.info("Not supported data type.")

    if array.ndim == 2:
        band_num = 1
    else:
        band_num = array.shape[2]

    raster_dir = os.path.dirname(new_raster)
    if not os.path.isdir(raster_dir):
        os.mkdir(raster_dir)

    out_raster = driver.Create(new_raster, cols, rows, band_num, gdt_d_type)
    out_raster.SetGeoTransform((origin_x, pixel_width, 0, origin_y, 0, pixel_height))

    out_band = None
    for b in range(band_num):
        out_band = out_raster.GetRasterBand(b + 1)
        if band_num == 1:
            out_band.WriteArray(array)
        else:
            out_band.WriteArray(array[:, :, b])
    out_band.SetNoDataValue(0)
    out_band.FlushCache()

    prj = dataset.GetProjection()
    out_raster = osr.SpatialReference(wkt=prj)
    out_raster.SetProjection(out_raster.ExportToWkt())


def list_of_files(filepath, patterns):
    """
    :param filepath:
    :param patterns:
    :return list_file_paths:
    """
    list_file_paths = []
    for file in os.listdir(filepath):
        if file.endswith(patterns):
            list_file_paths.append(file)
    return list_file_paths


def calc_cloud_mask(pan_filepath, mult_filepath, temp_path, erosion_radius, dilation_radius, is_pan):
    """
    :param pan_filepath:
    :param mult_filepath:
    :param temp_path:
    :param erosion_radius:
    :param dilation_radius:
    :param is_pan:
    :return cloud_mask:
    """
    mult_ds_img = gdal.Open(mult_filepath)
    cloud_mask = mult_ds_img.ReadAsArray()
    cloud_mask = np.rollaxis(cloud_mask, 0, 3)
    cloud_mask = (cloud_mask[:, :, 0] > 120) * (cloud_mask[:, :, 1] > 120) * (cloud_mask[:, :, 2] > 120) * \
                 (cloud_mask[:, :, 3] > 120) * (cloud_mask[:, :, 4] > 120) * (cloud_mask[:, :, 5] > 200) * \
                 (cloud_mask[:, :, 6] > 200)

    cloud_mask = erosion(cloud_mask, disk(erosion_radius))
    cloud_mask = dilation(cloud_mask, disk(dilation_radius))

    if is_pan:
        mask_filepath = os.path.join(temp_path, "mask.tif")
        with rasterio.open(pan_filepath) as ref_raster:
            ref_arr = ref_raster.read(1)
            ref_transform = ref_raster.transform

        array2raster(mask_filepath, mult_ds_img, cloud_mask, 'Byte')

        with rasterio.open(mask_filepath) as raster_to_resample:
            resampled_cloud_mask = raster_to_resample.read(
                out_shape=(raster_to_resample.count, ref_raster.height, ref_raster.width),
                resampling=rasterio.enums.Resampling.bilinear,
            )
        resampled_cloud_mask = np.rollaxis(resampled_cloud_mask, 0, 3)
        resampled_cloud_mask = np.squeeze(resampled_cloud_mask)

        cloud_mask = resampled_cloud_mask == 0
    return cloud_mask


def process_pan(pan_dir, mult_dir, reference_image, temp_path, output_dir, erosion_radius, dilation_radius):
    """
    :param pan_dir:
    :param mult_dir:
    :param reference_image:
    :param temp_path:
    :param output_dir:
    :param erosion_radius:
    :param dilation_radius:
    """
    pan_path_list = list_of_files(pan_dir, ('.tif', '.TIF', '.tiff', '.TIFF'))
    mult_path_list = list_of_files(mult_dir, ('.tif', '.TIF', '.tiff', '.TIFF'))

    reference = reference_image.GetRasterBand(1).ReadAsArray()
    idx_non_zeros_ref = (reference != 0)

    for item in pan_path_list:
        filepath = os.path.join(pan_dir, item)
        logging.info('Processing image {} of {}'.format(item, len(pan_path_list)))

        ds_img = gdal.Open(filepath)
        img = ds_img.GetRasterBand(1).ReadAsArray()
        img = np.uint8(img)

        img_name_pan = item.split('_')
        img_name_pan = '_' + img_name_pan[1] + '_' + img_name_pan[2] + '_' + img_name_pan[3]

        path_mult = next((s for s in mult_path_list if img_name_pan in s), None)
        filepath_mult = os.path.join(mult_dir, path_mult)

        cloud_mask = calc_cloud_mask(filepath, filepath_mult, temp_path, erosion_radius, dilation_radius, True)
        img = img * cloud_mask

        idx_non_zeros = (img != 0)
        pix_img_non_zeros = img[idx_non_zeros]
        ref = reference[idx_non_zeros_ref]

        lower, upper = np.percentile(ref, (1, 99))
        ref = (ref - lower) * (255 / (upper - lower))
        np.clip(ref, 0, 255, ref)
        ref = np.uint8(ref)
        matched = match_histograms(pix_img_non_zeros, ref, channel_axis=None)

        lower, upper = np.percentile(matched, (1, 99))
        matched = (matched - lower) * (255 / (upper - lower))
        np.clip(matched, 0, 255, matched)

        img[idx_non_zeros] = matched
        img = np.uint8(img)

        output_filename = os.path.join(output_dir, 'pan', item)
        array2raster(output_filename, ds_img, img, 'Byte')


def process_multi(mult_dir, reference_image, temp_path, output_dir, erosion_radius, dilation_radius):
    """
    :param mult_dir:
    :param reference_image:
    :param temp_path:
    :param output_dir:
    :param erosion_radius:
    :param dilation_radius:
    """
    mult_path_list = list_of_files(mult_dir, ('.tif', '.TIF', '.tiff', '.TIFF'))

    idx_non_zeros_ref = (reference_image[:, :, 0] != 0) * (reference_image[:, :, 1] != 0) * \
                        (reference_image[:, :, 2] != 0)

    for item in mult_path_list:
        filepath = os.path.join(mult_dir, item)
        logging.info('Processing image {} of {}'.format(item, len(mult_path_list)))

        ds_img = gdal.Open(filepath)
        img = ds_img.ReadAsArray()

        # TODO: use all bands
        img = np.rollaxis(img, 0, 3)
        img = np.stack((img[:, :, 4], img[:, :, 2], img[:, :, 1]))
        img = np.rollaxis(img, 0, 3)

        red = img[:, :, 0]
        green = img[:, :, 1]
        blue = img[:, :, 2]

        cloud_mask = calc_cloud_mask(None, filepath, temp_path, erosion_radius, dilation_radius, False)
        cloud_mask = cloud_mask == 0
        red = red * cloud_mask
        green = green * cloud_mask
        blue = blue * cloud_mask

        idx_non_zeros = (red != 0) * (green != 0) * (blue != 0)

        pix_img_non_zeros_red = red[idx_non_zeros]
        ref_red = reference_image[:, :, 0]
        ref_red = ref_red[idx_non_zeros_ref]
        matched_red = match_histograms(pix_img_non_zeros_red, ref_red, channel_axis=None)

        pix_img_non_zeros_green = green[idx_non_zeros]
        ref_green = reference_image[:, :, 1]
        ref_green = ref_green[idx_non_zeros_ref]

        matched_green = match_histograms(pix_img_non_zeros_green, ref_green, channel_axis=None)

        pix_img_non_zeros_blue = blue[idx_non_zeros]
        ref_blue = reference_image[:, :, 2]
        ref_blue = ref_blue[idx_non_zeros_ref]
        matched_blue = match_histograms(pix_img_non_zeros_blue, ref_blue, channel_axis=None)

        red[idx_non_zeros] = matched_red
        green[idx_non_zeros] = matched_green
        blue[idx_non_zeros] = matched_blue

        img_matched = np.stack((red, green, blue))
        img_matched = np.rollaxis(img_matched, 0, 3)
        img_matched = np.uint8(img_matched)

        output_filename = os.path.join(output_dir, 'mult', item)
        array2raster(output_filename, ds_img, img_matched, 'Byte')


def get_reference_image(path_img, is_pan):
    """
    :param path_img:
    :param is_pan:
    :return reference:
    """
    reference = gdal.Open(path_img)
    if is_pan:
        reference = reference.ReadAsArray()
        reference = np.rollaxis(reference, 0, 3)
        reference = np.stack((reference[:, :, 4], reference[:, :, 2], reference[:, :, 1]))
        reference = np.rollaxis(reference, 0, 3)
    return reference


def main(arguments):
    """
    :param arguments:
    """
    pan_ref_filepath = arguments.pan_ref_image
    mult_ref_filepath = arguments.mult_ref_image
    mult_dir = arguments.mult_dir
    pan_dir = arguments.pan_dir
    tmp_dir = arguments.tmp_dir
    output_dir = arguments.output_dir
    erosion_radius = int(arguments.erosion_radius)
    dilation_radius = int(arguments.dilation_radius)

    pan_ref_image = get_reference_image(pan_ref_filepath, True)
    process_pan(pan_dir, mult_dir, pan_ref_image, tmp_dir, output_dir, erosion_radius, dilation_radius)

    mult_ref_image = get_reference_image(mult_ref_filepath, False)
    process_multi(mult_dir, mult_ref_image, tmp_dir, output_dir, erosion_radius, dilation_radius)

    # TODO: deletar arquivos tmp
    # TODO: mensagem de finalização


if __name__ == '__main__':
    """ 
    Command-line routine for equalize satellite images (for now, WorldView-3 datasets). A procedure 
    to mask clouds is also performed. In this function, a single image is used as reference to equalize 
    all the other images. The reference image can be from another area.
    
    Optional arguments:
      -h, --help                                            Show this help message and exit
      -k, --pan_ref_image                                   Absolute filepath to the PAN reference image
      -z, --mult_ref_image                                  Absolute filepath to the MULT reference image
      -m, --mult_dir                                        Absolute directory to the multispectral images (TIF, TIFF)
      -p, --pan_dir                                         Absolute directory to the panchromatic images (TIF, TIFF)
      -t, --tmp_dir                                         Absolute directory to the temp files
      -o, --output_dir                                      Absolute directory to the output files
      -e, --erosion_radius                                  Integer value for erosion morphological procedure
      -d, --dilation_radius                                 Integer value for dilation morphological procedure
      -v, --verbose                                         Boolean to print output logging or not
      
    Usage:
        > python equalize_mosaic_cloud_mask.py -k STRING_FILEPATH -z STRING_FILEPATH -m STRING_PATH -p STRING_PATH
                                               -t STRING_PATH -o STRING_PATH -e INTEGER -d INTEGER 
                                               -v BOOLEAN
    Example:
        > python equalize_mosaic_cloud_mask.py -k /media/rodolfo/data/bioverse/trees/regions/kayapo/images/original-images/wv3/non-equalized/bioverse_2_1_012954101_10_0/012954101010_01_003/012954101010_01/012954101010_01_P001_PAN/16JUN19140331-P3DS_R03C1-012954101010_01_P001.TIF
                                               -z /media/rodolfo/data/bioverse/trees/regions/kayapo/images/original-images/wv3/non-equalized/bioverse_2_1_012954101_10_0/012954101010_01_003/012954101010_01/012954101010_01_P001_MUL/16JUN19140331-M3DS_R02C2-012954101010_01_P001.TIF                                               
                                               -m /media/rodolfo/data/bioverse/trees/regions/kayapo/images/original-images/wv3/non-equalized/bioverse_2_1_012954101_10_0/012954101010_01_003/012954101010_01/012954101010_01_P001_MUL/
                                               -p /media/rodolfo/data/bioverse/trees/regions/kayapo/images/original-images/wv3/non-equalized/bioverse_2_1_012954101_10_0/012954101010_01_003/012954101010_01/012954101010_01_P001_PAN/
                                               -t tmp/
                                               -o /media/rodolfo/data/bioverse/trees/regions/kayapo/images/original-images/wv3/equalized-2/
                                               -e 7 -d 27 -v True       
    """
    parser = argparse.ArgumentParser(description='Prepare input files for supervised neural network procedures')

    parser.add_argument('-k', '-pan_ref_image', action="store", dest='pan_ref_image',
                        help='Absolute filepath to the PAN reference image')
    parser.add_argument('-z', '-mult_ref_image', action="store", dest='mult_ref_image',
                        help='Absolute filepath to the MULT reference image')
    parser.add_argument('-m', '-mult_dir', action="store", dest='mult_dir',
                        help='Absolute directory to the multispectral images (TIF, TIFF)')
    parser.add_argument('-p', '-pan_dir', action="store", dest='pan_dir',
                        help='Absolute directory to the panchromatic images (TIF, TIFF)')
    parser.add_argument('-t', '-tmp_dir', action="store", dest='tmp_dir',
                        help='Absolute directory to the temp files')
    parser.add_argument('-o', '-output_dir', action="store", dest='output_dir',
                        help='Absolute directory to the temp files')
    parser.add_argument('-e', '-erosion_radius', action="store", dest='erosion_radius',
                        help='Integer value for erosion morphological procedure')
    parser.add_argument('-d', '-dilation_radius', action="store", dest='dilation_radius',
                        help='Integer value for dilation morphological procedure')
    parser.add_argument('-v', '-verbose', action="store", dest='verbose', help='Boolean (True or False) '
                                                                               'for printing log or not')

    args = parser.parse_args()

    if eval(args.verbose):
        log = logging.getLogger('')

        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        cf = ColoredFormatter("[%(asctime)s] {%(filename)-15s:%(lineno)-4s} %(levelname)-5s: %(message)s ")
        ch.setFormatter(cf)
        log.addHandler(ch)

        fh = logging.FileHandler('logging.log')
        fh.setLevel(logging.INFO)
        ff = logging.Formatter("[%(asctime)s] {%(filename)-15s:%(lineno)-4s} %(levelname)-5s: %(message)s ",
                               datefmt='%Y.%m.%d %H:%M:%S')
        fh.setFormatter(ff)
        log.addHandler(fh)

        log.setLevel(logging.DEBUG)
    else:
        logging.basicConfig(format="%(levelname)s: %(message)s")

    main(args)
