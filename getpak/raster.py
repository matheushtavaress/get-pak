import os
import json
import rasterio
import pkg_resources

from osgeo import gdal
from datetime import datetime
from rasterio.warp import calculate_default_transform, reproject, Resampling


class Raster:
    '''
    Generic class containing methods for matricial manipulations
    
    Methods
    -------
    array2tiff(ndarray_data, str_output_file, transform, projection, no_data=-1, compression='COMPRESS=PACKBITS')
        Given an input ndarray and the desired projection parameters, create a raster.tif using GDT_Float32.
    
    reproj(in_raster, out_raster, target_crs='EPSG:4326')
        Given an input raster.tif reproject it to reprojected.tif using @target_crs
    '''
    def __init__(self, parent_log=None):
            if parent_log:
                self.log = parent_log
            s2projdata = pkg_resources.resource_stream(__name__, 'data/s2_proj_ref.json')
            byte_content = s2projdata.read()
            self.s2projgrid = json.loads(byte_content)

    @staticmethod
    def array2tiff(ndarray_data, str_output_file, transform, projection, no_data=-1, compression='COMPRESS=PACKBITS'):
        '''
        Given an input ndarray and the desired projection parameters, create a raster.tif using GDT_Float32.
        
        Parameters
        ----------
        @param ndarray_data: Inform if the index should be saved as array in the output folder
        @param str_output_file:
        @param transform:
        @param projection:
        @param no_data:
        @param compression:

        @return: None (If all goes well, array2tiff should pass and generate a file inside @str_output_file)
        '''
        # Create file using information from the template
        outdriver = gdal.GetDriverByName("GTiff")  # http://www.gdal.org/gdal_8h.html
        # imgs_out = /work/scratch/guimard/grs2spm/
        [cols, rows] = ndarray_data.shape
        # GDT_Byte = 1, GDT_UInt16 = 2, GDT_UInt32 = 4, GDT_Int32 = 5, GDT_Float32 = 6,
        # options=['COMPRESS=PACKBITS'] -> https://gdal.org/drivers/raster/gtiff.html#creation-options
        outdata = outdriver.Create(str_output_file, rows, cols, 1, gdal.GDT_Float32, options=[compression])
        # Write the array to the file, which is the original array in this example
        outdata.GetRasterBand(1).WriteArray(ndarray_data)
        # Set a no data value if required
        outdata.GetRasterBand(1).SetNoDataValue(no_data)
        # Georeference the image
        outdata.SetGeoTransform(transform)
        # Write projection information
        outdata.SetProjection(projection)

        # Closing the files
        # https://gdal.org/tutorials/raster_api_tut.html#using-create
        data = None
        outdata = None
        pass
    
    @staticmethod
    def reproj(in_raster, out_raster, target_crs='EPSG:4326'):
        '''
        Given an input raster.tif reproject it to reprojected.tif using @target_crs (default = 'EPSG:4326').
        
        Parameters
        ----------
        @param in_raster: Inform if the index should be saved as array in the output folder
        @param out_raster:
        @param target_crs:
        
        @return: None (If all goes well, reproj should pass and generate a reprojected file inside @out_raster)
        '''
        # Open the input raster file
        with rasterio.open(in_raster) as src:

            # Calculate the transformation parameters
            transform, width, height = calculate_default_transform(
                src.crs, target_crs, src.width, src.height, *src.bounds)

            # Define the output file metadata
            kwargs = src.meta.copy()
            kwargs.update({
                'crs': target_crs,
                'transform': transform,
                'width': width,
                'height': height
            })

            # Create the output raster file
            with rasterio.open(out_raster, 'w', **kwargs) as dst:

                # Reproject the data
                for i in range(1, src.count + 1):
                    reproject(
                        source=rasterio.band(src, i),
                        destination=rasterio.band(dst, i),
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=transform,
                        dst_crs=target_crs,
                        resampling=Resampling.nearest)
        print(f'Done: {out_raster}')
        pass
    
class GRS:
    '''
    Core functionalities to handle GRS files

    Methods
    -------
    metadata(grs_file_entry)
        Given a GRS string element, return file metadata extracted from its name.
    '''
    def __init__(self, parent_log=None):
            if parent_log:
                self.log = parent_log
    
    @staticmethod
    def metadata(grs_file_entry):
        '''
        Given a GRS file return metadata extracted from its name:
        
        Parameters
        ----------
        @param grs_file_entry (str or pathlike obj): path that leads to the GRS.nc file.
                
        @return: metadata (dict) containing the extracted info, available keys are:
            input_file, basename, mission, prod_lvl, str_date, pydate, year,
            month, day, baseline_algo_version, relative_orbit, tile, 
            product_discriminator, cloud_cover, grs_ver.
        
        Reference
        ---------
        Given the following file:
        /root/23KMQ/2021/05/21/S2A_MSIL1C_20210521T131241_N0300_R138_T23KMQ_20210521T163353_cc020_v15.nc
        
        S2A : (MMM) is the mission ID(S2A/S2B)
        MSIL1C : (MSIXXX) Product procesing level
        20210521T131241 : (YYYYMMDDHHMMSS) Sensing start time
        N0300 : (Nxxyy) Processing Baseline number
        R138 : Relative Orbit number (R001 - R143)
        T23KMQ : (Txxxxx) Tile Number
        20210521T163353 : Product Discriminator
        cc020 : GRS Cloud cover estimation (0-100%)
        v15 : GRS algorithm baseline version

        Further reading:
        Sentinel-2 MSI naming convention:
        URL = https://sentinels.copernicus.eu/web/sentinel/user-guides/sentinel-2-msi/naming-convention
        '''
        metadata = {}
        basefile = os.path.basename(grs_file_entry)
        mission,proc_level,date_n_time,proc_ver,r_orbit,tile,prod_disc,cc,ver = basefile.split('_')
        file_event_date = datetime.strptime(date_n_time, '%Y%m%dT%H%M%S')
        yyyy = f"{file_event_date.year:02d}"
        mm = f"{file_event_date.month:02d}"
        dd = f"{file_event_date.day:02d}"
        
        metadata['input_file'] = grs_file_entry
        metadata['basename'] = basefile
        metadata['mission'] = mission
        metadata['prod_lvl'] = proc_level
        metadata['str_date'] = date_n_time
        metadata['pydate'] = file_event_date
        metadata['year'] = yyyy
        metadata['month'] = mm
        metadata['day'] = dd
        metadata['baseline_algo_version'] = proc_ver
        metadata['relative_orbit'] = r_orbit
        metadata['tile'] = tile
        metadata['product_discriminator'] = prod_disc
        metadata['cloud_cover'] = cc
        metadata['grs_ver'] = ver

        return metadata
