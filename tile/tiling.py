import os
import gdal
import logging
import glob
import shapefile
import geopandas as gp
import numpy as np
import settings

from cv2 import imread
from shapely.geometry import Polygon
from PIL import Image, ImageDraw

logging.getLogger('shapely.geos').setLevel(logging.CRITICAL)


class Tiling:
    """ Command-line routine to tile images and shapefiles according to desired width and heights """

    def __init__(self):
        """
        Constructor method
        """
        pass

    def slice_array(self, array, positions):
        """
        Auxiliar method to slice an array in small other array

        :param array: the input array
        :param positions: the position to be sliced
        :return: the new corresponded array list sliced
        """
        new_arrays = []
        positions.append(len(array) - 1)

        for i in range(len(positions) - 1):
            new_arrays.append(array[positions[i]:positions[i + 1]])

        return new_arrays

    def draw_class_id_label(self, width, height, classes, shapes, ext, x_ratio, y_ratio, records, output):
        """
        Auxiliar method to create a new label image in class id format, where the classes are represented by integer in
        a grayscale image. The image create have dimension width x height, based on the classes presented in the vector
        features

        :param width: a integer represented the image's width
        :param height: a integer represented the image's height
        :param classes: the classes to be checked in the vector records and to be interpreted by the method
        :param shapes: the vector features
        :param ext: the extends from the respective of vector file
        :param x_ratio: the aspect ratio in axis x, which determines the pixel size/dimension
        :param y_ratio: the aspect ratio in axis y, which determines the pixel size/dimension
        :param records: a list of records/rows from the vector content
        :param output: the absolute path to output file
        """
        img = Image.new("L", (width, height), "black")
        classes_content = classes['type']
        draw = ImageDraw.Draw(img)

        for i, record in enumerate(records):
            if record[1] in classes_content:
                parts = shapes[i].parts
                pixels = []

                fill_color = classes_content[record[1]]

                for x, y in shapes[i].points:
                    px = int(width - ((ext[3][0] - x) * x_ratio))
                    py = int((ext[3][1] - y) * y_ratio)
                    pixels.append((px, py))

                if len(parts) > 1:
                    polygons_parts = self.slice_array(pixels, parts)
                    for k in range(len(polygons_parts)):
                        draw.polygon(polygons_parts[k], outline=None, fill=fill_color)
                else:
                    draw.polygon(pixels, outline=None, fill=fill_color)
        img.save(output)

    def draw_rgb_label(self, width, height, classes, shapes, ext, x_ratio, y_ratio, records, output):
        """
        Auxiliar method to create a new label image in rgb format, where the classes are represented by RGB colors in
        a 3 channel image. The image create have dimension width x height, based on the classes presented in the vector
        features

        :param width: a integer represented the image's width
        :param height: a integer represented the image's height
        :param classes: the classes to be checked in the vector records and to be interpreted by the method
        :param shapes: the vector features
        :param ext: the extends from the respective of vector file
        :param x_ratio: the aspect ratio in axis x, which determines the pixel size/dimension
        :param y_ratio: the aspect ratio in axis y, which determines the pixel size/dimension
        :param records: a list of records/rows from the vector content
        :param output: the absolute path to output file
        """
        img = Image.new("RGB", (width, height), "black")
        classes_content = classes['color']
        draw = ImageDraw.Draw(img)

        for i, record in enumerate(records):
            if record[1] in classes_content:
                parts = shapes[i].parts
                pixels = []

                fill_color = "rgb(" + str(classes_content[record[1]][0]) + ", " + \
                             str(classes_content[record[1]][1]) + ", " + str(classes_content[record[1]][2]) + ")"

                for x, y in shapes[i].points:
                    px = int(width - ((ext[3][0] - x) * x_ratio))
                    py = int((ext[3][1] - y) * y_ratio)
                    pixels.append((px, py))

                if len(parts) > 1:
                    polygons_parts = self.slice_array(pixels, parts)
                    for k in range(len(polygons_parts)):
                        draw.polygon(polygons_parts[k], outline=None, fill=fill_color)
                else:
                    draw.polygon(pixels, outline=None, fill=fill_color)
        img.save(output)

    def draw_one_hot_label(self, image_path, classes):
        """
        Auxiliar method to create a new label image in class id format, where the classes are represented by integer in
        a grayscale image. The image create have dimension width x height, based on the classes presented in the vector
        features

        :param image_path: the absolute path to image file
        :param classes: the classes to be checked in the vector records and to be interpreted by the method
        """
        im = imread(image_path, 0)
        one_hot = np.zeros((im.shape[0], im.shape[1], len(classes)))

        for i, unique_value in enumerate(np.unique(im)):
            one_hot[:, :, i][im == unique_value] = 1
        im = Image.fromarray(one_hot)
        im.save(image_path)

    def shp2png(self, raster_folder, shapefile_folder, output_folder, width, height, classes, label_type):
        """
        Transform the vector files in shapefile_folder, which has its correspondent image with same name in
        raster_folder (with geographic metadata information), in PNG image formats (labeled images), where each
        polygon in vector are read and draw according to the classes defined.

        Source:
            - https://github.com/GeospatialPython/geospatialpython/blob/master/shp2img.py

        Example of classes variable:
            classes = {
                    "def": [255, 255, 0],
                    "water": [102, 204, 255],
                    "cloud": [255, 255, 255],
                    "shadow": [128, 128, 128],
                    "other": [0, 0, 0],
                }

        :param raster_folder: the absolute path to raster, with all georeferenced information
        :param shapefile_folder: the absolute path to the vector file, with polygons representing the location
                                 of interest objects
        :param output_folder: the absolute path to the outputs
        :param width: the width of each tile presented in shapefile_folder
        :param height: the width of each tile presented in shapefile_folder
        :param classes: the classes to be found in vector file and to be draw in png format
        :param label_type: the type of label image. Options are: class_id, rgb or one_hot
        """
        files = os.listdir(shapefile_folder)
        shp_list = [file for file in files if file.endswith(settings.VALID_VECTOR_EXTENSION)]

        for shape in shp_list:
            name, file_extension = os.path.splitext(shape)
            shape_path = os.path.join(shapefile_folder, shape)
            output = os.path.join(output_folder, name + ".png")
            raster = os.path.join(raster_folder, name + ".tif")

            # TODO: the raster extension could vary from TIF to TIFF, tif, tiff, so on.
            if os.path.isfile(raster):
                tile = gdal.Open(raster)
                gt = tile.GetGeoTransform()
                cols_tile = tile.RasterXSize
                rows_tile = tile.RasterYSize
                ext = self.get_extent(gt, cols_tile, rows_tile)
            else:
                continue

            if os.path.isfile(shape_path):
                # TODO: to predict the encoding - hardcoded
                r = shapefile.Reader(shape_path, encoding='ISO8859-1')
                if not r:
                    logging.info('>>>> Error: could not open the shapefile')
                    continue
            else:
                logging.info('>>>> Error: could not open the shapefile')
                continue

            x_dist = ext[3][0] - ext[1][0]
            y_dist = ext[3][1] - ext[1][1]
            x_ratio = width / x_dist
            y_ratio = height / y_dist

            shapes = r.shapes()
            records = r.records()

            if label_type == 'class_id':
                self.draw_class_id_label(width, height, classes, shapes, ext, x_ratio, y_ratio, records, output)
            elif label_type == 'rgb':
                self.draw_rgb_label(width, height, classes, shapes, ext, x_ratio, y_ratio, records, output)
            elif label_type == 'one_hot':
                self.draw_rgb_label(width, height, classes, shapes, ext, x_ratio, y_ratio, records, output)
                self.draw_one_hot_label(output, classes)
            else:
                logging.warning(">>>>>> Wrong label type: {} . Options are: class_id, rgb or one_hot"
                                .format(label_type))

    def get_extent(self, gt, cols, rows):
        """
        Read and returns the extends bounds from a geographic raster in x,y coordinates

        Source:
            - https://gis.stackexchange.com/questions/57834/
              how-to-get-raster-corner-coordinates-using-python-gdal-bindings

        :param gt: the GeoTransform metadata from geographic raster tile
        :param cols: the number of columns in tile
        :param rows: the number of rows in tile
        :return: the converted extend bounds in x,y coordinates
        """
        ext = []
        x_arr = [0, cols]
        y_arr = [0, rows]

        for px in x_arr:
            for py in y_arr:
                x = gt[0] + (px * gt[1]) + (py * gt[2])
                y = gt[3] + (px * gt[4]) + (py * gt[5])
                ext.append([x, y])
            y_arr.reverse()
        return ext

    def tiling_raster(self, image, output_folder, width, height, strecthing=True):
        """
        Take a image with high dimensions, and tile it in small other pieces with dimension of width x height

        :param image: the absolute path to the image file (raster)
        :param output_folder: the absolute path to the outputs
        :param width: the width of the image
        :param height: the width of the image
        :param strecthing: default True. If False, the outputs will be save as it is the inputs
        """
        if os.path.isfile(image) and image.endswith(settings.VALID_RASTER_EXTENSION):
            filename = os.path.basename(image)
            name, file_extension = os.path.splitext(filename)
            ds = gdal.Open(image)
            datatype = ds.GetRasterBand(1).DataType
            dtype = gdal.GetDataTypeName(datatype)

            if ds is None:
                logging.warning(">>>>>> Could not open image file {}. Skipped!".format(image))

            rows = ds.RasterXSize
            cols = ds.RasterYSize
            tiles_cols = cols / width
            tiles_rows = rows / height

            logging.info(">>>> File {} opened! Image with [{}, {}] size and {} type!".format(image, rows, cols, dtype))
            logging.info(">> Tiling image {}. {} x {} pixels. Estimated {} tiles of {} x {}..."
                         .format(image, rows, cols, round(tiles_cols * tiles_rows), width, height))

            gdal.UseExceptions()
            for i in range(0, rows, width):
                for j in range(0, cols, height):
                    try:
                        output = os.path.join(output_folder, name + "_" + str(i) + "_" + str(j) + file_extension)

                        if settings.ALL_BANDS is True:
                            options = ['-epo', '-eco']
                        else:
                            options = ['-epo', '-eco',
                                       '-b', settings.RASTER_TILES_COMPOSITION[0],
                                       '-b', settings.RASTER_TILES_COMPOSITION[1],
                                       '-b', settings.RASTER_TILES_COMPOSITION[2]]

                        if strecthing is True:
                            stats = [ds.GetRasterBand(i + 1).GetStatistics(True, True) for i in range(ds.RasterCount)]
                            vmin, vmax, vmean, vstd = zip(*stats)
                            scale_params = [[list(zip(*[vmin, vmax]))]]
                        else:
                            scale_params = None

                        gdal.Translate(output, ds, format='GTIFF', srcWin=[i, j, width, height],
                                       outputType=datatype, scaleParams=scale_params,
                                       options=options)

                    except RuntimeError:
                        continue
        else:
            logging.info(">>>> Image file {} does not exist or it is an invalid extension!".format(image))
        logging.info(">>>> Done")

    def tiling_vector(self, image_tiles_folder, shp_reference, output_folder):
        """
        Take a vector file and tile it according to the extend's image presented in image_tiles_folder
        :param image_tiles_folder: the absolute path to the image file (raster)
        :param shp_reference: the vector file to be tiled, which shares the same region as the
                              images presented in image_tiles_folder
        :param output_folder: the absolute path to the outputs
        """
        if not os.path.isdir(image_tiles_folder):
            logging.warning(">>>> {} is not a folder!".format(image_tiles_folder))
            return

        if not os.path.isfile(shp_reference):
            logging.warning(">>>> {} is not a file!".format(shp_reference))
            return

        filename = os.path.basename(shp_reference)
        name, file_extension = os.path.splitext(filename)

        if file_extension.lower() not in settings.VALID_VECTOR_EXTENSION:
            logging.warning(">>>> {} not a valid extension for a vector!".format(file_extension))
            return

        list_correspondent_raster = glob.glob(os.path.join(image_tiles_folder, name + '*'))
        if len(list_correspondent_raster) == 0:
            logging.info(">>>> No raster tiles with shapefile suffix {}".format(name))
            return

        logging.info(">> Tiling vector {} respecting to the tiles extends".format(shp_reference))
        for image in list_correspondent_raster:
            filename = os.path.basename(image)
            name, ext = os.path.splitext(filename)

            if ext.lower() not in settings.VALID_RASTER_EXTENSION:
                logging.warning(">>>> {} not a valid extension for a raster!".format(ext))
                continue

            output = os.path.join(output_folder, name + ".shp")
            complete_path = os.path.join(image_tiles_folder, image)
            tile = gdal.Open(complete_path)

            gt = tile.GetGeoTransform()
            cols_tile = tile.RasterXSize
            rows_tile = tile.RasterYSize
            ext = self.get_extent(gt, cols_tile, rows_tile)

            bounds = Polygon(ext)
            baseshp = gp.read_file(shp_reference)
            # baseshp = baseshp.to_crs(epsg=32722)

            if os.path.isfile(output):
                continue
            else:
                ids = []
                classes = []
                polygons_intersecting = []
                for i in range(len(baseshp)):
                    p1 = baseshp['geometry'][i]
                    p2 = bounds

                    if p1 is None:
                        logging.info(">>>>>> Geometry is empty! File {}".format(os.path.basename(shp_reference)))
                        continue

                    if p1.is_valid is False:
                        p1 = p1.buffer(0)

                    if not p1.intersection(p2).is_empty:
                        ids.append(i)
                        classes.append(baseshp[settings.CLASS_NAME][i])
                        polygons_intersecting.append(p1.intersection(p2))

                if len(polygons_intersecting) != 0:
                    gdf = gp.GeoDataFrame()
                    gdf.crs = baseshp.crs
                    gdf['id'] = ids
                    gdf['class'] = classes
                    gdf['geometry'] = polygons_intersecting
                    gdf.to_file(output, driver='ESRI Shapefile')
                    logging.info(">>>> Raster {} intersect {}. Vector tile {} created!".
                                 format(complete_path, os.path.basename(shp_reference), output))
                else:
                    logging.warning(">>>> Raster {} does not intersect {}. Discarted!".
                                    format(complete_path, os.path.basename(shp_reference)))
                    os.remove(complete_path)
        logging.info(">>>> Done")


