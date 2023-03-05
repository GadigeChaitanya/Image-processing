# Equalizing and mask clouds using WorldView-3 dataset
The script `equalize_mosaic_cloud_mask.py` has the aim to equalize a set of WorldView-3 dataset using a reference image to normalize all the set. Besides, it has also the ability to mask all the clouds (not the shadow), making the histogram equalization even more accurate.

## Parameters
```
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
```

## Example of usage
```
python equalize_mosaic_cloud_mask.py -k /media/rodolfo/data/bioverse/trees/regions/kayapo/images/original-images/wv3/non-equalized/bioverse_2_1_012954101_10_0/012954101010_01_003/012954101010_01/012954101010_01_P001_PAN/16JUN19140331-P3DS_R03C1-012954101010_01_P001.TIF -z /media/rodolfo/data/bioverse/trees/regions/kayapo/images/original-images/wv3/non-equalized/bioverse_2_1_012954101_10_0/012954101010_01_003/012954101010_01/012954101010_01_P001_MUL/16JUN19140331-M3DS_R02C2-012954101010_01_P001.TIF -m /media/rodolfo/data/bioverse/trees/regions/kayapo/images/original-images/wv3/non-equalized/bioverse_2_1_012954101_10_0/012954101010_01_003/012954101010_01/012954101010_01_P001_MUL/ -p /media/rodolfo/data/bioverse/trees/regions/kayapo/images/original-images/wv3/non-equalized/bioverse_2_1_012954101_10_0/012954101010_01_003/012954101010_01/012954101010_01_P001_PAN/ -t tmp/ -o /media/rodolfo/data/bioverse/trees/regions/kayapo/images/original-images/wv3/equalized-2/ -e 7 -d 27 -v True
```

```
python equalize_mosaic_cloud_mask.py -k /media/rodolfo/data/bioverse/trees/regions/kayapo/images/original-images/wv3/non-equalized/bioverse_2_1_012954101_10_0/012954101010_01_003/012954101010_01/012954101010_01_P001_PAN/16JUN19140331-P3DS_R03C1-012954101010_01_P001.TIF -z /media/rodolfo/data/bioverse/trees/regions/kayapo/images/original-images/wv3/non-equalized/bioverse_2_1_012954101_10_0/012954101010_01_003/012954101010_01/012954101010_01_P001_MUL/16JUN19140331-M3DS_R02C2-012954101010_01_P001.TIF -m /media/rodolfo/data/bioverse/trees/regions/kayapo/images/original-images/wv3/non-equalized/bioverse_2_2_012954102_10_0/012954102010_01_003/012954102010_01/012954102010_01_P001_MUL/ -p /media/rodolfo/data/bioverse/trees/regions/kayapo/images/original-images/wv3/non-equalized/bioverse_2_2_012954102_10_0/012954102010_01_003/012954102010_01/012954102010_01_P001_PAN/ -t tmp/ -o /media/rodolfo/data/bioverse/trees/regions/kayapo/images/original-images/wv3/equalized-2/ -e 7 -d 27 -v True
```