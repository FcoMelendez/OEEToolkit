#!/usr/bin/python

from pydoc import resolve
import sys, getopt
import logging
import threading
import time
from tkinter import Pack
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
    self.lastAssetState = {}
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
  
  def readAssetState(self):
    url = "http://"+str(self.broker_ip)+":"+str(self.broker_port)+"/v2/entities/"+str(self.entity_id)+"/attrs/assetPackMLState?metadata=dateModified"
    state = None
    payload={}
    headers = {}
    response = requests.request("GET", url, headers=headers, data=payload)
    responseDict = json.loads(response.text)
    #if self.lastAssetState != {}:
    #  if self.lastAssetState["metadata"]["dateModified"]["value"]==responseDict["metadata"]["dateModified"]["value"]:
    #    state = None
    #  else:
    #    state = responseDict["value"]
    #self.lastAssetState=responseDict
    state = responseDict["value"]
    return state

  def sendOeeData(self, A,P,Q,OEE):
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
    self.idealDurationOfExecuteStateInSecs = 4
    self.availabilityDurationInSecs = 0
    self.executeStateTimerInSecs = 0 
    self.goodPartCount = 0
    self.totalPartCount = 0
    self.totalDurationTimerInSecs = 1
    self.anomaliesCount = 0
    self.anomaliesDurationTimer = 0
    self.plannedBreaksCount = 0
    self.plannedBreaksDurationTimerInSecs = 0
    self.currentPartExecutionTimerInSecs = 0

  def setAvailability(self, value):
    self.A = value
    return self.A
  def setPerformance(self, value):
    self.P = value
    return self.P
  def setQuality(self, value):
    self.Q = value
    return self.Q
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
  # - Event 2  (Transition): IDLE2EXECUTE
  # - Event 3  (Transition): IDLE2ABORTED
  # - Event 4  (Transition): IDLE2STOPPED
  # - Event 5  (Continuity): EXECUTE2EXECUTE
  # - Event 6  (Transition): EXECUTE2STOPPED
  # - Event 7  (Transition): EXECUTE2ABORTED
  # - Event 8  (Continuity): STOPPED2STOPPED
  # - Event 9  (Transition): STOPPED2IDLE
  # - Event 10 (Transition): STOPPED2IABORTED
  # - Event 11 (Continuity): ABORTED2ABORTED
  # - Event 12 (Transition): ABORTED2STOPPED
  #
  # The function below identifies the event associated to each incoming asset state
  # and reflects the effects of such events in the OEE algorithm variables

  def onOeeEvent(self, newAssetState, timeBetweenStateSamplesInSecs):
    print("---")
    print(PackMLStates.IDLE.name)
    
    if self.lastAssetState == PackMLStates.IDLE.name:
      if newAssetState == PackMLStates.IDLE.name:
        # IDLE2IDLE Event: The machine is available
        self.availabilityDurationInSecs += timeBetweenStateSamplesInSecs
      elif newAssetState == PackMLStates.EXECUTE.name:
        # IDLE2EXECUTE The machine is available + The production a new Part starts
        self.availabilityDurationInSecs += timeBetweenStateSamplesInSecs
        self.currentPartExecutionTimerInSecs = 0
      elif newAssetState == PackMLStates.STOPPED.name:
        # IDLE2STOPPED The machine becomes NOT available due to a planned BREAK
        self.plannedBreaksCount += 1
      elif newAssetState == PackMLStates.ABORTED.name:
        # IDLE2ABORTED The machine becomes NOT available with some anomaly/issue
        self.anomaliesCount += 1
    
    if self.lastAssetState == PackMLStates.EXECUTE.name:
      if newAssetState == PackMLStates.EXECUTE.name:
        # EXECUTE2EXECUTE Event: The machine is available + the execution time of the current part increases
        self.availabilityDurationInSecs += timeBetweenStateSamplesInSecs
        self.executeStateTimerInSecs += timeBetweenStateSamplesInSecs
        self.currentPartExecutionTimerInSecs += timeBetweenStateSamplesInSecs
      elif newAssetState == PackMLStates.STOPPED.name:
        # EXECUTE2STOPPED Event: The machine becomes NOT available + a new GOOD part is produced
        self.goodPartCount += 1
        self.totalPartCount += 1 
        self.plannedBreaksCount +=1 
      elif newAssetState == PackMLStates.ABORTED.name:
        # EXECUTE2ABORTED Event: The machine becomes NOT available + the current part was a BAD part
        self.anomaliesCount += 1
        self.totalPartCount += 1 
        self.executeStateTimerInSecs -= self.currentPartExecutionTimerInSecs

    if self.lastAssetState == PackMLStates.STOPPED.name:
      if newAssetState == PackMLStates.STOPPED.name:
        #STOPPED2STOPPED Event: The machine remains NOT available 
        self.plannedBreaksDurationTimerInSecs += timeBetweenStateSamplesInSecs
      elif newAssetState == PackMLStates.IDLE.name:
        #STOPPED2IDLE Event: The machine is available again
        self.availabilityDurationInSecs += timeBetweenStateSamplesInSecs
      elif newAssetState == PackMLStates.ABORTED.name:
        #STOPPED2ABORTED Event: The machine is NOT available + some anomaly/issue happened
        self.anomaliesCount += 1
    
    if self.lastAssetState == PackMLStates.ABORTED.name:
      if newAssetState == PackMLStates.ABORTED.name:
        self.anomaliesDurationTimer += 1
      elif newAssetState == PackMLStates.STOPPED.name:
        self.plannedBreaksCount += 1
    
    self.lastAssetState = newAssetState
    self.totalDurationTimerInSecs += timeBetweenStateSamplesInSecs

  # There are multiple ways to calculate OEE subindexes (i.e., Availability, Performance, Quality).
  # For instance, depending on each business case events like "planned breaks" or "short unavailability periods"
  # may be considered as Availability losses in one company while a seond company considers them as Performance losses.
  # The current implementation considers:
  #
  # Availability Losses: Every single time unit that the machine is not in IDLE or EXECUTE mode is an Avaliability Loss
  #                       --> Availability = Sum of IDLE & EXECUTE time periods / Sum of all state periods
  # Performance Losses: Only the execution time associated to Good Parts is taken into account for Performance losses.
  #                     · Given an ideal part production ratio in secs per part. The ideal performance is expressed as 
  #                       --> Ideal Count of Parts = Time dedicated to produced Good Parts / Ideal Part Production Ratio
  #                     · The actual performance value is then calculated as
  #                       --> Performance = Actual count of Good Parts / Ideal Count of Parts
  # Quality Losses: Every transition from IDLE to EXECUTE counts as a new part. Every execution that does not result in 
  #                 a good part is a Quality loss.
  #                       --> Quality = Good Parts Produced / Total Parts Tried 
  #
  # The functions below calculate A, P, and Q indexes based on the variables of the algorithm developed 
  # for this OEE Toolkit

  def calculateAvailabilityIndex(self):
    availability = self.availabilityDurationInSecs / self.totalDurationTimerInSecs
    print("OEE subindex - Availability")
    print("  idealAvailabilityDuration (seconds): ", self.totalDurationTimerInSecs)
    print("  actualAvailabilityDuration (seconds): ", self.availabilityDurationInSecs)
    print("  AVAILABILITY:",availability)
    return self.setAvailability(availability)
  
  def calculatePerformanceIndex(self):
    performance = 0
    referencePerformanceUnit = self.idealDurationOfExecuteStateInSecs
    referenceProductionTime = self.executeStateTimerInSecs
    referenceGoodPartCount = referenceProductionTime / referencePerformanceUnit
    if referenceGoodPartCount>0:
      performance = self.goodPartCount / referenceGoodPartCount
    print("OEE subindex - Performance")
    print("  Ideal Number of Parts: ", referenceGoodPartCount)
    print("  Actual Number of Parts: ", self.goodPartCount)
    print("  PERFORMANCE:", performance)
    return self.setPerformance(performance)
  
  def calculateQualityIndex(self):
    quality = 0
    if self.totalPartCount>0:  
      quality = self.goodPartCount / self.totalPartCount
    print("OEE subindex - Quality")
    print("  Total Parts: ", self.totalPartCount)
    print("  Actual Good Parts: ", self.goodPartCount)
    print("  QUALITY:", quality)
    return self.setQuality(quality)


def main_thread_function(name, A, P, Q):
  n = 0
  ngsiv2Obj = ngsiv2Interface("localhost", 1026, "myAsset") 
  oeeObj = OeeObject(A,P,Q)
  oeeValue = oeeObj.getOEE()
  print("The OEE is: ", oeeValue)
  ngsiv2Obj.sendOeeData(A,P,Q,oeeValue)
  lastStateTimestamp = int(time.time())
  currentStateTimestamp = int(time.time())
  while n<100:
    # Read Asset State
    currentStateTimestamp = int(time.time())
    currentState = ngsiv2Obj.readAssetState()
    if currentState != None:
      timeBetweenSamplesInSecs = currentStateTimestamp - lastStateTimestamp
      lastStateTimestamp = currentStateTimestamp
      logging.info("Thread %s: Asset state is: %s", name, currentState)
      # Execute on Event Function
      oeeObj.onOeeEvent(currentState, timeBetweenSamplesInSecs)
      # calculate OEE subindexes
      Av = oeeObj.calculateAvailabilityIndex()
      Pe = oeeObj.calculatePerformanceIndex()
      Qu = oeeObj.calculateQualityIndex()
      # Get OEE values
      OEE = oeeObj.getOEE()
      ngsiv2Obj.sendOeeData(Av, Pe, Qu, OEE)
    else:
      logging.info("Thread %s: Waiting for a new asset state")
    time.sleep(1)
    n+=1
  
  logging.info("Thread %s: Finishing...", name)

def main(argv):
  a = 0
  p = 0
  q = 0
  try:
    opts, args = getopt.getopt(argv,"ha:p:q:",["availability=","performance=","quality="])
  except getopt.GetoptError:
    print ('oeetoolkit.py -a <availability> -p <performance> -q <quality>')
    sys.exit()
  for opt, arg in opts:
    if opt == '-h':
      print ('oeetoolkit.py -a <availability> -p <performance> -q <quality>')
      sys.exit()
    elif opt in ("-a", "--availability"):
      a = arg
      print ("A is ", a)
    elif opt in ("-p", "--performance"):
      p = arg
      print ("P is ", p)
    elif opt in ("-q", "--quality"):
      q = arg
      print ("Q is ", q)

  format = "%(asctime)s: %(message)s"
  logging.basicConfig(format=format, level=logging.INFO, datefmt="%H:%M:%S")
  logging.info("Main    : Creating the main thread of the OEE microservice")
  x = threading.Thread(target=main_thread_function, args=["OEE", a,p,q])
  logging.info("Main    : Starting the main thread of the OEE microservice")
  x.start()
  logging.info("Main    : waiting for the main thread of the OEE microservice to finish")
  x.join()
  logging.info("Main    : all done")

if __name__ == "__main__":
  main(sys.argv[1:])
