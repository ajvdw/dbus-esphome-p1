#!/usr/bin/env python
# vim: ts=2 sw=2 et

# import normal packages
import platform 
import logging
import logging.handlers
import sys
import os
import sys
if sys.version_info.major == 2:
    import gobject
else:
    from gi.repository import GLib as gobject
import sys
import time
import requests # for http GET
import configparser # for config/ini file
 
# our own packages from victron
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python'))
from vedbus import VeDbusService


class DbusESPHomeP1Service:
    def __init__(self, paths, productname='ESPHome P1', connection='ESPHome P1 HTTP JSOn service'):
        config = self._getConfig()
        deviceinstance = int(config['DEFAULT']['DeviceInstance'])
        customname = config['DEFAULT']['CustomName']
        role = 'grid'
        servicename = 'com.victronenergy.' + role
        productid = 45069

        self._dbusservice = VeDbusService("{}.http_{:02d}".format(servicename, deviceinstance))
        self._paths = paths

        self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
        self._dbusservice.add_path('/Mgmt/Connection', connection)
    
        # Create the mandatory objects
        self._dbusservice.add_path('/DeviceInstance', deviceinstance)
        self._dbusservice.add_path('/ProductId', productid)
        self._dbusservice.add_path('/DeviceType', 345) # found on https://www.sascha-curth.de/projekte/005_Color_Control_GX.html#experiment - should be an ET340 Engerie Meter
        self._dbusservice.add_path('/ProductName', productname)
        self._dbusservice.add_path('/CustomName', customname)
        self._dbusservice.add_path('/Latency', None)
        self._dbusservice.add_path('/FirmwareVersion', 0.2)
        self._dbusservice.add_path('/HardwareVersion', 0)
        self._dbusservice.add_path('/Connected', 1)
        self._dbusservice.add_path('/Role', role)
        self._dbusservice.add_path('/Position', 0) 
        self._dbusservice.add_path('/Serial', self._getP1Serial())
        self._dbusservice.add_path('/UpdateIndex', 0)
        
        # add path values to dbus
        for path, settings in self._paths.items():
          self._dbusservice.add_path(
            path, settings['initial'], gettextcallback=settings['textformat'], writeable=True, onchangecallback=self._handlechangedvalue)
    
        # last update
        self._lastUpdate = 0
    
        # add _update function 'timer'
        gobject.timeout_add(500, self._update) # pause 500ms before the next request
        
        # add _signOfLife 'timer' to get feedback in log every 5minutes
        gobject.timeout_add(self._getSignOfLifeInterval()*60*1000, self._signOfLife)
    
    def _getP1Serial(self):
        meter_data = self._getP1Data()  
        
        if not meter_data['unique_id']:
            raise ValueError("Response does not contain 'unique_id' attribute")
        
        serial = meter_data['unique_id']
        return serial

    def _getConfig(self):
        config = configparser.ConfigParser()
        config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))
        return config;
 
 
    def _getSignOfLifeInterval(self):
        config = self._getConfig()
        value = config['DEFAULT']['SignOfLifeLog']
        
        if not value: 
            value = 0
        
        return int(value)


    def _getP1StatusUrl(self):
        config = self._getConfig()
        URL = "http://%s/text_sensor/p1data" % (config['DEFAULT']['Host'])
        return URL
  
  
    def _getP1Data(self):
        URL = self._getP1StatusUrl()
        resp_data = requests.get(url = URL, timeout=5)
  
        # check for response
        if not resp_data:
            raise ConnectionError("No response from endpoint - %s" % (URL))

        p1data = resp_data.json()             
        # check for Json
        if not p1data:
           raise ValueError("Converting response to JSON failed")

        p1json = eval(p1data["value"])
    
        meter_data={};
        meter_data["unique_id"] = p1json[0]
        meter_data["active_voltage_l1_v"] = p1json[1][0]
        meter_data["active_voltage_l2_v"] = p1json[1][1]
        meter_data["active_voltage_l3_v"] = p1json[1][2]
        meter_data["active_current_l1_a"] = p1json[2][0]
        meter_data["active_current_l2_a"] = p1json[2][1]
        meter_data["active_current_l3_a"] = p1json[2][2]
        meter_data["active_power_l1_w"] = p1json[3][0]
        meter_data["active_power_l2_w"] = p1json[3][1]
        meter_data["active_power_l3_w"] = p1json[3][2]
        meter_data["active_power_w"] = p1json[4]
        meter_data["total_power_import_kwh"] = p1json[5]
        meter_data["total_power_export_kwh"] = p1json[6]  
        return meter_data
  
  
    def _signOfLife(self):
        logging.info("--- Start: sign of life ---")
        logging.info("Last _update() call: %s" % (self._lastUpdate))
        logging.info("Last '/Ac/Power': %s" % (self._dbusservice['/Ac/Power']))
        logging.info("--- End: sign of life ---")
        return True
 
    def _update(self):   
        try:
            #get data from P1 meter
            meter_data = self._getP1Data()
            config = self._getConfig()

            #send data to DBus for 3phase system
            self._dbusservice['/Ac/Power'] = meter_data['active_power_w']
            self._dbusservice['/Ac/L1/Voltage'] = meter_data['active_voltage_l1_v']
            self._dbusservice['/Ac/L2/Voltage'] = meter_data['active_voltage_l2_v']
            self._dbusservice['/Ac/L3/Voltage'] = meter_data['active_voltage_l3_v']
            self._dbusservice['/Ac/L1/Current'] = meter_data['active_current_l1_a']
            self._dbusservice['/Ac/L2/Current'] = meter_data['active_current_l2_a']
            self._dbusservice['/Ac/L3/Current'] = meter_data['active_current_l3_a']
            self._dbusservice['/Ac/L1/Power'] = meter_data['active_power_l1_w']
            self._dbusservice['/Ac/L2/Power'] = meter_data['active_power_l2_w']
            self._dbusservice['/Ac/L3/Power'] = meter_data['active_power_l3_w']
            self._dbusservice['/Ac/Energy/Forward'] = (meter_data['total_power_import_kwh'])
            self._dbusservice['/Ac/Energy/Reverse'] = (meter_data['total_power_export_kwh'])
         
            
            #logging
            logging.debug("Grid Consumption (/Ac/Power): %s" % (self._dbusservice['/Ac/Power']))
            logging.debug("Grid Forward (/Ac/Energy/Forward): %s" % (self._dbusservice['/Ac/Energy/Forward']))
            logging.debug("Grid Reverse (/Ac/Energy/Revers): %s" % (self._dbusservice['/Ac/Energy/Reverse']))
            logging.debug("---");
            
            # increment UpdateIndex - to show that new data is available an wrap
            self._dbusservice['/UpdateIndex'] = (self._dbusservice['/UpdateIndex'] + 1 ) % 256

            #update lastupdate vars
            self._lastUpdate = time.time()
        except (ValueError, requests.exceptions.ConnectionError, requests.exceptions.Timeout, ConnectionError) as e:
            logging.critical('Error getting data from Shelly - check network or Shelly status. Setting power values to 0. Details: %s', e, exc_info=e)       
            self._dbusservice['/Ac/L1/Power'] = 0                                       
            self._dbusservice['/Ac/L2/Power'] = 0                                       
            self._dbusservice['/Ac/L3/Power'] = 0
            self._dbusservice['/Ac/Power'] = 0
            self._dbusservice['/UpdateIndex'] = (self._dbusservice['/UpdateIndex'] + 1 ) % 256        
        except Exception as e:
            logging.critical('Error at %s', '_update', exc_info=e)
        
        # return true, otherwise add_timeout will be removed from GObject - see docs http://library.isr.ist.utl.pt/docs/pygtk2reference/gobject-functions.html#function-gobject--timeout-add
        return True
    
    def _handlechangedvalue(self, path, value):
        logging.debug("someone else updated %s to %s" % (path, value))
        return True # accept the change

  
  
  
  
def getLogLevel():
    config = configparser.ConfigParser()
    config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))
    logLevelString = config['DEFAULT']['LogLevel']
    
    if logLevelString:
        level = logging.getLevelName(logLevelString)
    else:
        level = logging.INFO
        
    return level


def main():
    #configure logging
    logging.basicConfig(format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        level=getLogLevel(),
        handlers=[
            logging.FileHandler("%s/current.log" % (os.path.dirname(os.path.realpath(__file__)))),
            logging.StreamHandler()
        ])
 
    try:
        logging.info("Start");
    
        from dbus.mainloop.glib import DBusGMainLoop
        # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
        DBusGMainLoop(set_as_default=True)
        
        #formatting 
        _kwh = lambda p, v: (str(round(v, 2)) + ' kWh')
        _a = lambda p, v: (str(round(v, 1)) + ' A')
        _w = lambda p, v: (str(round(v, 1)) + ' W')
        _v = lambda p, v: (str(round(v, 1)) + ' V')   
        
        #start our main-service
        
        pvac_output = DbusESPHomeP1Service(
            paths={
                '/Ac/Energy/Forward': {'initial': 0, 'textformat': _kwh}, # energy bought from the grid
                '/Ac/Energy/Reverse': {'initial': 0, 'textformat': _kwh}, # energy sold to the grid
                '/Ac/Power': {'initial': 0, 'textformat': _w},
                
                '/Ac/Current': {'initial': 0, 'textformat': _a},
                '/Ac/Voltage': {'initial': 0, 'textformat': _v},
                
                '/Ac/L1/Voltage': {'initial': 0, 'textformat': _v},
                '/Ac/L2/Voltage': {'initial': 0, 'textformat': _v},
                '/Ac/L3/Voltage': {'initial': 0, 'textformat': _v},
                '/Ac/L1/Current': {'initial': 0, 'textformat': _a},
                '/Ac/L2/Current': {'initial': 0, 'textformat': _a},
                '/Ac/L3/Current': {'initial': 0, 'textformat': _a},
                '/Ac/L1/Power': {'initial': 0, 'textformat': _w},
                '/Ac/L2/Power': {'initial': 0, 'textformat': _w},
                '/Ac/L3/Power': {'initial': 0, 'textformat': _w},
                '/Ac/L1/Energy/Forward': {'initial': 0, 'textformat': _kwh},
                '/Ac/L1/Energy/Reverse': {'initial': 0, 'textformat': _kwh},
                })
        logging.info('Connected to dbus, and switching over to gobject.MainLoop() (= event based)')
        mainloop = gobject.MainLoop()
        mainloop.run()            
    except (ValueError, requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        logging.critical('Error in main type %s', str(e))
    except Exception as e:
        logging.critical('Error at %s', 'main', exc_info=e)
        
if __name__ == "__main__":
    main()
