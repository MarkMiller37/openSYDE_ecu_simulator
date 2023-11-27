import ecu_config as ecu_config
import time
from loggers.logger_app import logger

#service IDs
DIAGNOSTIC_SESSION_CONTROL_SID = 0x10
ECU_RESET_SID = 0x11
READ_DATA_BY_ID_SID = 0x22
SECURITY_ACCESS_SID = 0x27
WRITE_DATA_BY_ID_SID = 0x2E
ROUTINE_CONTROL_SID = 0x31
TESTER_PRESENT_SID = 0x3E
READ_DP_DATA_EVENT_DRIVEN = 0xBA
READ_DP_DATA_BY_ID = 0xBB
WRITE_DP_DATA_BY_ID = 0xBC

#routine control routines
RC_ROUTINE_READ_DATAPOOL_META_DATA           = 0x0211
RC_ROUTINE_VERIFY_DATAPOOL                   = 0x0212

#diagnostic session
#DEFAULT = 1
#EXTENDED_DIAGNOSIS = 3
#PREPROGRAMMING = 0x60
#PROGRAMMING = 2
DIAGNOSTIC_SESSION_TYPES = [0x01, 0x03, 0x60, 0x02]
DIAGNOSTIC_SESSION_PARAMETER_RECORD = [0x00, 0x1E, 0x0B, 0xB8]

#ECU reset parameters
ECU_RESET_ENABLE_RAPID_POWER_SHUT_DOWN = 0x04
ECU_RESET_POWER_DOWN_TIME = 0x0F

POSITIVE_RESPONSE_SID_MASK = 0x40

NEGATIVE_RESPONSE_SID = 0x7F

#negative response codes
NRC_SUB_FUNCTION_NOT_SUPPORTED = 0x12
NRC_INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT = 0x13
NRC_REQUEST_OUT_OF_RANGE = 0x31

#current state of ECU simulation
current_session = DIAGNOSTIC_SESSION_TYPES[0]
current_data_rates = [100,500,1000]
#list of currently configured event based transmissions
#elements: "data_pool", "list", "element", "rail", "last_send_time"
current_event_based_transmissions = []
current_last_event_based_send_times = [0,0,0]

#data pool definition
datapool_1_elements = [
   { "list": 0, "element": 0, "size": 2 },
   { "list": 0, "element": 1, "size": 2 },
   { "list": 0, "element": 2, "size": 2 },
   { "list": 0, "element": 3, "size": 2 },
   { "list": 0, "element": 4, "size": 1 },
   { "list": 0, "element": 5, "size": 1 },
   { "list": 0, "element": 6, "size": 1 },
   { "list": 0, "element": 7, "size": 1 },
   { "list": 0, "element": 8, "size": 1 },
   { "list": 0, "element": 9, "size": 1 },
]

datapool_information = [
   { "version": bytes([0,0,0]), "name": "J1939", "elements": datapool_1_elements }
 ]


#table of defined services
SERVICES = [
    {"id": DIAGNOSTIC_SESSION_CONTROL_SID, "description": "DiagnosticSessionControl", "response": lambda request: get_diagnostic_session_control_response(request)},
    {"id": READ_DATA_BY_ID_SID, "description": "ReadDataById", "response": lambda request: get_read_data_by_id_response(request)},
    {"id": SECURITY_ACCESS_SID, "description": "SecurityAccess", "response": lambda request: get_security_access_response(request)},
    {"id": ROUTINE_CONTROL_SID, "description": "RoutineControl", "response": lambda request: get_routine_control_response(request)},
    {"id": WRITE_DATA_BY_ID_SID, "description": "WriteDataById", "response": lambda request: get_write_data_by_id_response(request)},
    {"id": READ_DP_DATA_BY_ID, "description": "ReadDpDataById", "response": lambda request: get_read_dp_data_by_id_response(request)},
    {"id": READ_DP_DATA_EVENT_DRIVEN, "description": "ReadDpDataEventDriven", "response": lambda request: get_read_dp_data_event_driven_response(request)},
    {"id": TESTER_PRESENT_SID, "description": "TesterPresent", "response": lambda request: get_tester_present_response(request)}
]


def process_service_request(request):
    if request is not None and len(request) >= 1:
        sid = request[0]
        for service in SERVICES:
            if service.get("id") == sid:
                logger.info("Requested UDS SID " + hex(sid) + ": " + service.get("description"))
                return service.get("response")(request)
        logger.warning("Requested SID " + hex(sid) + " not supported")
    else:
        logger.warning("Invalid request")
        return None


def get_diagnostic_session_control_response(request):
    if len(request) == 2:
        session_type = request[1]
        if session_type in DIAGNOSTIC_SESSION_TYPES:
            current_session = session_type
            return get_positive_response_sid(DIAGNOSTIC_SESSION_CONTROL_SID) + bytes([session_type]) \
                   + bytes(DIAGNOSTIC_SESSION_PARAMETER_RECORD)
        return get_negative_response(DIAGNOSTIC_SESSION_CONTROL_SID,  NRC_SUB_FUNCTION_NOT_SUPPORTED)
    return get_negative_response(DIAGNOSTIC_SESSION_CONTROL_SID,  NRC_INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT)


def get_read_data_by_id_response(request):
    if len(request) == 3:
        identifier = request[1] << 8 | request[2]
        logger.info("ReadDataById: Requested ID " + hex(identifier) + ".")
        match identifier:
            case 0xF186:
                logger.info("Id: ActiveDiagnosticSession")
                positive_response = get_positive_response_sid(READ_DATA_BY_ID_SID) + bytes([request[1], request[2], current_session])
                return positive_response
            case _:
               return get_negative_response(READ_DATA_BY_ID_SID, NRC_SUB_FUNCTION_NOT_SUPPORTED)
    return get_negative_response(READ_DATA_BY_ID_SID, NRC_INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT)


def get_security_access_response(request):
    if len(request) > 1:
        sub_function = request[1]
        if sub_function % 2 != 0:
            #odd value: request seed
            logger.info("RequestSeed Level " + hex(sub_function))
            #respond with "42" seed in any case
            positive_response = get_positive_response_sid(SECURITY_ACCESS_SID) + bytes([sub_function]) + bytes([0,0,0,42])
            return positive_response
        else:
            #even value: send key
            logger.info("SendKey Level " + hex(sub_function - 1))
            if len(request) != 6:
                return get_negative_response(READ_DATA_BY_ID_SID, NRC_INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT)
            else:
                #we are always happy :-)
                positive_response = get_positive_response_sid(SECURITY_ACCESS_SID) + bytes([sub_function]) 
                return positive_response
    return get_negative_response(READ_DATA_BY_ID_SID, NRC_INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT)


def get_routine_control_response(request):
    if len(request) > 3:
        sub_function = request[1]
        routine_id = request[2] << 8 | request[3]
        match sub_function:
            case 1:
                mode_string = "start"
            case 2:
                mode_string = "stop"
            case 3:
                mode_string = "requestresults"
            case _:
                mode_string = "undefinedsubfunction" + hex(sub_function)
        if routine_id == RC_ROUTINE_READ_DATAPOOL_META_DATA:
            if sub_function == 1 and len(request) > 4:
                data_pool_index = request[4]
                logger.info(mode_string + "Routine: ReadDataPoolMetaData  DataPool: " + hex(request[4]))
                if data_pool_index < len(datapool_information):
                    #format of response:
                    #[01] followed by three byte version info
                    #[02] followed by length of name and name as string
                    data_pool_name = datapool_information[data_pool_index].get("name")
                    positive_response = get_positive_response_sid(ROUTINE_CONTROL_SID) + \
                                        bytes([request[1], request[2], request[3], request[4]]) + \
                                        bytes([1]) + \
                                        datapool_information[data_pool_index].get("version") + \
                                        bytes([2, len(data_pool_name)]) + bytes(data_pool_name, 'utf-8')
                    return positive_response
                else:
                    logger.info(mode_string + "Unknown DataPool")
                    #NRC_REQUEST_OUT_OF_RANGE: let client know this DP does not exist
                    return get_negative_response(ROUTINE_CONTROL_SID, NRC_REQUEST_OUT_OF_RANGE)
            else:
                logger.info(mode_string + "Routine: ReadDataPoolMetaData: incorrect DLC or sub-function")
                return get_negative_response(ROUTINE_CONTROL_SID, NRC_INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT)
        elif routine_id == RC_ROUTINE_VERIFY_DATAPOOL:
            if sub_function == 1 and len(request) > 8:
                data_pool_index = request[4]
                checksum = request[5] << 24 | request[6] << 16 | request[7] << 8 | request[8]
                logger.info(mode_string + "Routine: VerifyDataPool  DataPool: " + hex(request[4]) + "  Checksum: " + hex(checksum))
                if data_pool_index < len(datapool_information):
                    data_pool_name = datapool_information[data_pool_index].get("name")
                    positive_response = get_positive_response_sid(ROUTINE_CONTROL_SID) + \
                                        bytes([request[1], request[2], request[3], request[4]]) + \
                                        bytes([0]) #0: checksum matches; we are happy
                    return positive_response
                else:
                    logger.info(mode_string + "Unknown DataPool")
                    return get_negative_response(ROUTINE_CONTROL_SID, NRC_REQUEST_OUT_OF_RANGE)
            else:
                logger.info(mode_string + "Routine: VerifyDataPool: incorrect DLC or sub-function")
                return get_negative_response(ROUTINE_CONTROL_SID, NRC_INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT)
        else:
            logger.info(mode_string + "Routine: Unknown routine: " + hex(routine_id))
            return get_negative_response(ROUTINE_CONTROL_SID, NRC_INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT)
    return get_negative_response(ROUTINE_CONTROL_SID, NRC_INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT)


def get_write_data_by_id_response(request):
    if len(request) > 2:
        identifier = request[1] << 8 | request[2]
        logger.info("WriteDataById: Requested ID " + hex(identifier) + ".")
        match identifier:
            case 0xA810:
                if len(request) > 4:
                   current_data_rates[0] = request[3] << 8 | request[4]
                   logger.info("Id: DataRate1  Rate: " + hex(current_data_rates[0] ) + ".")
                   return get_positive_response_sid(WRITE_DATA_BY_ID_SID) + bytes([request[1], request[2]])
                else:
                   logger.info("Incorrect DLC")
                   return get_negative_response(WRITE_DATA_BY_ID_SID, NRC_INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT)
            case 0xA811:
                if len(request) > 4:
                   current_data_rates[1] = request[3] << 8 | request[4]
                   logger.info("Id: DataRate2  Rate: " + hex(current_data_rates[1] ) + ".")
                   return get_positive_response_sid(WRITE_DATA_BY_ID_SID) + bytes([request[1], request[2]])
                else:
                   logger.info("Incorrect DLC")
                   return get_negative_response(WRITE_DATA_BY_ID_SID, NRC_INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT)
            case 0xA812:
                if len(request) > 4:
                   current_data_rates[2] = request[3] << 8 | request[4]
                   logger.info("Id: DataRate3  Rate: " + hex(current_data_rates[2] ) + ".")
                   return get_positive_response_sid(WRITE_DATA_BY_ID_SID) + bytes([request[1], request[2]])
                else:
                   logger.info("Incorrect DLC")
                   return get_negative_response(WRITE_DATA_BY_ID_SID, NRC_INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT)
            case _:
               return get_negative_response(WRITE_DATA_BY_ID_SID, NRC_SUB_FUNCTION_NOT_SUPPORTED)
    return get_negative_response(WRITE_DATA_BY_ID_SID, NRC_INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT)


def get_read_dp_data_by_id_response(request):
    if len(request) == 4:
        data_pool_index = (request[1] >> 2) & 0x1F
        list_index = ((request[1] << 8 | request[2]) >> 3) & 0x7F
        element_index = (request[2] << 8 | request[3]) & 0x7FF
        logger.info("ReadDpDataById: Requested ID " + hex(data_pool_index) + "." + hex(list_index) + "." + hex(element_index))
        if data_pool_index < len(datapool_information):
           for element in datapool_information[data_pool_index].get("elements"):
               if (element.get("list") == list_index) and (element.get("element") == element_index):
                   #element known
                   element_size = element.get("size")
                   #to get non-zero values we return the size as value of all returned bytes
                   return get_positive_response_sid(READ_DP_DATA_BY_ID) + bytes([request[1], request[2], request[3]]) + \
                          bytes([element_size] * element_size)
           return get_negative_response(READ_DP_DATA_BY_ID, NRC_REQUEST_OUT_OF_RANGE)
        else:
           logger.info("Unknown DataPool")
           return get_negative_response(READ_DP_DATA_BY_ID, NRC_REQUEST_OUT_OF_RANGE)
    return get_negative_response(READ_DP_DATA_BY_ID, NRC_INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT)

def get_read_dp_data_event_driven_response(request):
    if (len(request) == 2) and (request[1] == 0):
        #stop all
        current_event_based_transmissions.clear()
        logger.info("ReadDpDataEventDriven: StopAll")
        return get_positive_response_sid(READ_DP_DATA_EVENT_DRIVEN) + bytes(request[1])
    elif len(request) >= 5:
        rail = request[1]
        data_pool_index = (request[2] >> 2) & 0x1F
        list_index = ((request[2] << 8 | request[3]) >> 3) & 0x7F
        element_index = (request[3] << 8 | request[4]) & 0x7FF
        if len(request) == 9:
           rail -= 4
           logger.info("ReadDpDataEventDriven: Requested ID " + hex(data_pool_index) + "." + hex(list_index) + "." + hex(element_index) + \
                       "  Type: onchange  Rail: " + hex(rail))
        else:
           rail -= 1
           logger.info("ReadDpDataEventDriven: Requested ID " + hex(data_pool_index) + "." + hex(list_index) + "." + hex(element_index) + \
                       "  Type: cyclic  Rail: " + hex(rail))

        #do we know the requested element ?
        found = False
        if data_pool_index < len(datapool_information):
           for element in datapool_information[data_pool_index].get("elements"):
               if (element.get("list") == list_index) and (element.get("element") == element_index):
                   #element known
                   element_size = element.get("size")
                   if element_size <= 4:
                      found = True
                      break
           if found == False:
               return get_negative_response(READ_DP_DATA_EVENT_DRIVEN, NRC_REQUEST_OUT_OF_RANGE)
        else:
           logger.info("Unknown DataPool")
           return get_negative_response(READ_DP_DATA_EVENT_DRIVEN, NRC_REQUEST_OUT_OF_RANGE)

        #threshold will be ignored; does not really bother client if we send too often
        new_transmission = {"data_pool": data_pool_index, "list": list_index, "element": element_index, "rail": rail }
        found = False
        #if entry already exists replace it; otherwise append:
        for transmission in current_event_based_transmissions:
            if transmission.get("data_pool") == data_pool_index and transmission.get("list") == list_index and \
               transmission.get("element") == element:
                transmission = new_transmission
                found = True
                break
        if found == False:
           current_event_based_transmissions.append(new_transmission)
        #send initial response:
        return get_positive_response_sid(READ_DP_DATA_EVENT_DRIVEN) + bytes([request[2], request[3], request[4]])
    return get_negative_response(READ_DP_DATA_EVENT_DRIVEN, NRC_INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT)
 

def send_event_based_responses():
    responses = []

    now_ms = time.monotonic_ns() / 1000 / 1000
    for rail in range(3):
       if (current_last_event_based_send_times[rail] + current_data_rates[rail] <= now_ms):
           current_last_event_based_send_times[rail] = now_ms
           
           #send all transmissions on that rail:
           for transmission in current_event_based_transmissions:
               if transmission.get("rail") == rail:
                   data_pool_index = transmission.get("data_pool")
                   list_index = transmission.get("list")
                   element_index = transmission.get("element")

                   #find element in DP:
                   for element in datapool_information[data_pool_index].get("elements"):
                       if (element.get("list") == list_index) and (element.get("element") == element_index):
                           element_size = element.get("size")
                           #to get non-zero values we use now_ms
                           response = get_positive_response_sid(READ_DP_DATA_EVENT_DRIVEN) + bytes( \
                                      [(data_pool_index << 2) | (list_index >> 5), \
                                      ((list_index) << 3) | (element_index >> 8), \
                                      element_index & 0xFF]) +\
                                      bytes([int(now_ms) & 0xFF] * element_size)
                           responses.append(response)
                           break
    return responses


def get_tester_present_response(request):
    #ignore
    return None


def is_reset_type_supported(reset_type):
    return 0x05 >= reset_type >= 0x01


def get_positive_response_sid(requested_sid):
    return bytes([requested_sid + POSITIVE_RESPONSE_SID_MASK])


def get_negative_response(sid, nrc):
    logger.warning("Negative response for SID " + hex(sid) + " will be sent")
    return bytes([NEGATIVE_RESPONSE_SID]) + bytes([sid]) + bytes([nrc])
