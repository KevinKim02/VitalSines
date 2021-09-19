'''
    Initial configuration for USB-1608fs-Plus DAQ devices
    Detects connected devices by the passed board number and adds the available device to the Universal Library.

'''

from __future__ import absolute_import, division, print_function
from builtins import *  # @UnusedWildImport
from mcculw import ul
from mcculw.enums import InterfaceType
import sys

def config_first_detected_device(board_num, dev_id_list=None):

    # -- Detect InstaCal configuration error
    try:
        ul.ignore_instacal()
    except OSError:
        print('  ERROR: INSTACAL OS ERROR\n')
        sys.exit()
    
    devices = ul.get_daq_device_inventory(InterfaceType.ANY)
    if not devices:
        raise Exception('Error: No DAQ devices found')

    '''
    Connection Log:

    print('Found', len(devices), 'DAQ device(s):')
    for device in devices:
        print('  ', device.product_name, ' (', device.unique_id, ') - ',
              'Device ID = ', device.product_id, sep='')
    '''

    # -- List of all connected devices
    device = devices[board_num]

    if dev_id_list:
        device = next((device for device in devices
                       if device.product_id in dev_id_list), None)

        # -- No DAQ device connected
        if not device:
            err_str = 'Error: No DAQ device found in device ID list: '
            err_str += ','.join(str(dev_id) for dev_id in dev_id_list)
            raise Exception(err_str)

    # -- Add the DAQ device associated with the board number to the Universal Library
    ul.create_daq_device(board_num, device)
