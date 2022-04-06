#!/usr/bin/python

import sys, getopt
import logging
import threading
import time
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
    self.connect(ctxBroker_ip,ctxBroker_port,entity_id)
  
  def connect(self, broker_ip, broker_port, entity_id_str):
    id_str = str(entity_id_str)
    url = "http://"+str(broker_ip)+":"+str(broker_port)+"/v2/entities/"+id_str+"/attrs"
    headers = {'Content-Type': 'application/json'}
    payload = dict()
    payload["oeeAvailability"] = {"type":"number", "value":0.0}
    json_payload = json.dumps(payload, indent = 2)
    response = requests.request("POST", url, headers=headers, data=json_payload)
    print(response.text)
    payload = dict()
    payload["oeePerformance"] = {"type":"number", "value":0.0}
    json_payload = json.dumps(payload, indent = 2)
    response = requests.request("POST", url, headers=headers, data=json_payload)
    print(response.text)
    payload = dict()
    payload["oeeQuality"] = {"type":"number", "value":0.0}
    json_payload = json.dumps(payload, indent = 2)
    response = requests.request("POST", url, headers=headers, data=json_payload)
    print(response.text)
    payload = dict()
    payload["oeeValue"] = {"type":"number", "value":0.0}
    json_payload = json.dumps(payload, indent = 2)
    response = requests.request("POST", url, headers=headers, data=json_payload)
    print(response.text)
    payload = dict()
    payload["assetPackMLState"] = {"type":"string", "value":PackMLStates.STOPPED.name}
    json_payload = json.dumps(payload, indent = 2)
    response = requests.request("POST", url, headers=headers, data=json_payload)
    print(response.text)

  def sendData(self, A,P,Q,OEE):
    id_str = str(self.entity_id)
    url = "http://"+str(self.broker_ip)+":"+str(self.broker_port)+"/v2/entities/"+id_str+"/attrs"
    headers = {'Content-Type': 'application/json'}
    payload = dict()
    payload["oeeAvailability"] = {"type":"number", "value":A}
    json_payload = json.dumps(payload, indent = 2)
    response = requests.request("POST", url, headers=headers, data=json_payload)
    print(response.text)
    payload = dict()
    payload["oeePerformance"] = {"type":"number", "value":P}
    json_payload = json.dumps(payload, indent = 2)
    response = requests.request("POST", url, headers=headers, data=json_payload)
    print(response.text)
    payload = dict()
    payload["oeeQuality"] = {"type":"number", "value":Q}
    json_payload = json.dumps(payload, indent = 2)
    response = requests.request("POST", url, headers=headers, data=json_payload)
    print(response.text)
    payload = dict()
    payload["oeeValue"] = {"type":"number", "value":OEE}
    json_payload = json.dumps(payload, indent = 2)
    response = requests.request("POST", url, headers=headers, data=json_payload)
    print(response.text)
     
class OeeObject:
  def __init__(self, A, P, Q):
    self.OEE = 0
    self.A = float(A)
    self.P = float(P)
    self.Q = float(Q)
    self.lastAssetState = None
    self.samplingRateInSecs = 1
    self.idealDurationOfExecuteState = 5
    self.availabilityDurationInSecs = 0
    self.executeStateTimer = 0 
    self.goodPartCounter = 0
    self.totalPartCounter = 0
    self.totalDurationTimer = 0

  def setAvailability(self, value):
    self.A = value
  def setPerformance(self, value):
    self.P = value
  def setQuality(self, value):
    self.Q = value
  def getOEE(self):
    self.OEE = self.A * self.P * self.Q
    print("OEE is ", self.OEE )
    return self.OEE
  
  # Not all PackML states have to be used in every machine.
  # Wowever, there is a set of mandatory states. Mandatory states are: IDLE, EXECUTE, STOPPED, and ABORTED.
  # - The OEE effects depend on the comparison of the last two state readings.
  # - Each new reading along with the previous one determine an OEE event
  # - OEE events impact the OEE value

  # Consecutive readings must meet some continuity/transition requirements. 
  # According to the PackML standard, valid and invalid pairs exist.
  # The following function  includes the valid pairs and determines the impact of each of them in the OEE. 
  # - Event 1  (Continuity): IDLE2IDLE
  # - Event 2  (Continuity): EXECUTE2EXECUTE
  # - Event 3  (Continuity): STOPPED2STOPPED
  # - Event 4  (Continuity): ABORTED2ABORTED
  # - Event 5  (Transition): IDLE2EXECUTE
  # - Event 6  (Transition): IDLE2ABORTED
  # - Event 7  (Transition): EXECUTE2STOPPED
  # - Event 8  (Transition): EXECUTE2ABORTED
  # - Event 9  (Transition): STOPPED2IDLE
  # - Event 10 (Transition): ABORTED2STOPPED

  def onOeeEvent(self, newAssetState):
    
    if self.lastAssetState == PackMLStates.IDLE.name:
      if newAssetState == PackMLStates.IDLE.name:
        self.availabilityDurationInSecs += self.samplingRateInSecs
      elif newAssetState == PackMLStates.EXECUTE.name:
        self.availabilityDurationInSecs += self.samplingRateInSecs
        self.totalPartCounter += 1 
      elif newAssetState == PackMLStates.ABORTED.name:
        self.availabilityDurationInSecs += 0
    
    if self.lastAssetState == PackMLStates.EXECUTE.name:
      if newAssetState == PackMLStates.EXECUTE.name:
        self.availabilityDurationInSecs += self.samplingRateInSecs
        self.executeStateTimer += self.samplingRateInSecs
      elif newAssetState == PackMLStates.STOPPED.name:
        self.goodPartCounter += 1 
      elif newAssetState == PackMLStates.ABORTED.name:
        self.availabilityDurationInSecs += 0
    
    if self.lastAssetState == PackMLStates.STOPPED.name:
      if newAssetState == PackMLStates.STOPPED.name:
        self.availabilityDurationInSecs += 0
      elif newAssetState == PackMLStates.IDLE.name:
        self.availabilityDurationInSecs += 1
    
    if self.lastAssetState == PackMLStates.ABORTED.name:
      if newAssetState == PackMLStates.ABORTED.name:
        self.availabilityDurationInSecs += 0
      elif newAssetState == PackMLStates.STOPPED.name:
        self.availabilityDurationInSecs += 0
    
    self.totalDurationTimer += 1



def main_thread_function(name):
  n = 0
  while n<10:
    logging.info("Thread %s: starting", name)
    time.sleep(2)
    logging.info("Thread %s: finishing", name)
    n+=1

def main(argv):
  ngsiv2Obj = ngsiv2Interface("localhost", 1026, "myAsset")
  format = "%(asctime)s: %(message)s"
  logging.basicConfig(format=format, level=logging.INFO, datefmt="%H:%M:%S")
  logging.info("Main    : before creating thread")
  x = threading.Thread(target=main_thread_function, args=(1,))
  logging.info("Main    : before running thread")
  x.start()
  logging.info("Main    : wait for the thread to finish")
  x.join()
  logging.info("Main    : all done")
  
  A = 0
  P = 0
  Q = 0
  try:
    opts, args = getopt.getopt(argv,"ha:p:q:",["availability=","performance=","quality="])
  except getopt.GetoptError:
    print ('oeetoolkit.py -a <availability> -p <performance> -q <quality>')
    sys.exit(2)
  for opt, arg in opts:
    if opt == '-h':
      print ('oeetoolkit.py -a <availability> -p <performance> -q <quality>')
      sys.exit()
    elif opt in ("-a", "--availability"):
      A = arg
      print ("A is ", A)
    elif opt in ("-p", "--performance"):
      P = arg
      print ("P is ", P)
    elif opt in ("-q", "--quality"):
      Q = arg
      print ("Q is ", Q)
  oeeObj = OeeObject(A,P,Q)
  oeeValue = oeeObj.getOEE()
  print("The OEE is: ", oeeValue)
  ngsiv2Obj.sendData(A,P,Q,oeeValue)

if __name__ == "__main__":
  main(sys.argv[1:])
