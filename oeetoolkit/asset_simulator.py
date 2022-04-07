import sys, getopt
import logging
import threading
import time
from pyrsistent import b
import requests
import json
from enum import Enum

class PackMLStates(Enum):
  STOPPED = 1
  RESETTING = 2
  IDLE = 3
  STARTING = 4
  EXECUTE = 5
  COMPLETING = 6
  COMPLETE = 7
  HOLDING = 8
  HELD = 9
  UNHOLDING = 10
  SUSPENDING = 11
  SUSPENDED = 12
  UNSUSPENDING = 13
  ABORTING = 14
  ABORTED = 15
  CLEARING = 16
  STOPPING = 17 


class ngsiv2Interface:
  def __init__(self, ctxBroker_ip, ctxBroker_port, entity_id):
    self.broker_ip = ctxBroker_ip
    self.broker_port = ctxBroker_port  
    self.entity_id = entity_id
    # create attributes
    # - oeeAvailability
    # - oeePerformance
    # - oeeQuality
    # - oeeValue
    # - assetPackMLState
    self.onConnect(ctxBroker_ip,ctxBroker_port,entity_id)
  
  def onConnect(self, broker_ip, broker_port, entity_id_str):
    id_str = str(entity_id_str)
    url = "http://"+str(broker_ip)+":"+str(broker_port)+"/v2/entities/"
    headers = {'Content-Type': 'application/json'}
    payload = dict()
    # Asset Header
    payload["id"] = id_str
    payload["type"] = "I40Asset"
    # Static Asset Attributes
    payload["name"] = {"type":"string", "value":"Robot"}
    # Asset Telemetry
    payload["assetPackMLState"] = {"type":"string", "value": PackMLStates.STOPPED.name}
    json_payload = json.dumps(payload, indent = 2)
    response = requests.request("POST", url, headers=headers, data=json_payload)
    print(response)
  
  def sendAssetTelemetry(self, telemetryDict):
    url = "http://"+str(self.broker_ip)+":"+str(self.broker_port)+"/v2/entities/"+str(self.entity_id)+"/attrs"  
    payload = json.dumps(telemetryDict, indent = 2)
    headers = {'Content-Type': 'application/json'}
    response = requests.request("PATCH", url, headers=headers, data=payload)
    print(response)
      


def main_thread_function(name):
  n = 0
  i = 0
  ngsiv2Obj = ngsiv2Interface("localhost", 1026, "myAsset") 
  states = [PackMLStates.STOPPED.name, PackMLStates.IDLE.name, PackMLStates.EXECUTE.name, PackMLStates.EXECUTE.name, PackMLStates.STOPPED.name,
            PackMLStates.IDLE.name, PackMLStates.EXECUTE.name, PackMLStates.EXECUTE.name, PackMLStates.STOPPED.name, PackMLStates.STOPPED.name]
  assetTelemetry = dict()
  assetTelemetry["assetPackMLState"] ={"type":"string", "value": PackMLStates.STOPPED.name}
  while n<100:
    # Read Asset State
    assetTelemetry["assetPackMLState"]["value"] = states[i]
    # Send Asset Telemetry
    ngsiv2Obj.sendAssetTelemetry(assetTelemetry)
    time.sleep(2.5)
    n+=1
    i+=1
    if i==10:
      i=0
  logging.info("Thread %s: Finishing...", name)

def main(argv):

  format = "%(asctime)s: %(message)s"
  logging.basicConfig(format=format, level=logging.INFO, datefmt="%H:%M:%S")
  logging.info("Main    : Creating the main thread of the OEE microservice")
  x = threading.Thread(target=main_thread_function, args=["Asset Simulator"])
  logging.info("Main    : Starting the main thread of the OEE microservice")
  x.start()
  logging.info("Main    : waiting for the main thread of the OEE microservice to finish")
  x.join()
  logging.info("Main    : all done")

if __name__ == "__main__":
  main(sys.argv[1:])