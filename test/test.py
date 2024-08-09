#!/usr/bin/env python

# import normal packages
import sys
import os
import sys
import json
import requests # for http GET

def main():

    URL = 'http://slimmemeter.local/text_sensor/p1data'

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

    for key, value in meter_data.items():
        print(key, ":", value)
        
if __name__ == "__main__":
    main()
