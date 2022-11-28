from fhir.resources.bundle import Bundle, BundleEntry
from fhir.resources.reference import Reference
from fhir.resources.task import Task
from fhir.resources.messageheader import MessageHeader
from fhir.resources.practitionerrole import PractitionerRole
from fhir.resources.patient import Patient
from fhir.resources.observation import Observation
from fhir.resources.servicerequest import ServiceRequest
from fhir.resources.codeableconcept import CodeableConcept
import util.bundleparser as parser
import services.operation_outcome_builder as oobuilder
import logging
import uuid

# Minimal Bundle:
#  MessageHeader
#  Task
#  ServiceRequest
#  Patient
#  Initiator PractitionerRole
#  Initiator Practitioner
#  Initiator Organization
#  Recipient PractitionerRole
#  Recipient Organization

currently_supported_actions = ["accept", "decline", "updateprogress", "confirmcancellation", "complete"]

service_request_profile = "http://hl7.org/fhir/us/bser/StructureDefinition/BSeR-ReferralServiceRequest"
task_profile = "http://hl7.org/fhir/us/bser/StructureDefinition/BSeR-ReferralTask"
initiator_practitioner_role_profile = "http://hl7.org/fhir/us/bser/StructureDefinition/BSeR-ReferralInitiatorPractitionerRole"
recipient_practitioner_role_profile = "http://hl7.org/fhir/us/bser/StructureDefinition/BSeR-ReferralRecipientPractitionerRole"

logger = logging.getLogger("bserfeedbackapi.services.feedback_bundle_builder")

def create_feedback(request_bundle: Bundle, action: str, status_message: str):
    # Require status_message if action is update progress.
    if action.lower() == "updateprogress".lower() and not status_message:
        return oobuilder.build_missing_status_message_operation_outcome()

    # Parse Existing Bundle
    # Add list of missing expected resources to return as OperationOutcome
    missing_resources = []

    try:
        service_request = parser.find_resource_by_profile(request_bundle, service_request_profile)
        # Remove extraneous Supporting Info for demo purposes, and simplify references.
        service_request.supportingInfo = [Reference(**{"display": "Referral Request Document Bundle Omitted for Simplicity"})]
        service_request = ServiceRequest(**parser.simplify_references(service_request))
    except LookupError as e:
        service_request = None
        logger.error(str(e))
        missing_resources.append("Service Request")
    
    try:
        patient = parser.find_subject(request_bundle, service_request)
    except LookupError as e:
        patient = None
        logger.error(str(e))
        missing_resources.append("Patient")

    try:
        task = parser.find_resource_by_profile(request_bundle, task_profile)
        task = Task(**parser.simplify_references(task))
    except LookupError as e:
        task = None
        logger.error(str(e))
        missing_resources.append("Task")
    
    try:
        initiator_practitioner_role = parser.find_resource_by_profile(request_bundle, initiator_practitioner_role_profile)
        initiator_practitioner_role = PractitionerRole(**parser.simplify_references(initiator_practitioner_role))
        # Strip the Endpoint and Healthcare Services for now for simplicity. No need to echo them back.
        # TODO: Generalize this for non BSeR Engine created bundles.
        initiator_practitioner_role.healthcareService = None
        initiator_practitioner_role.endpoint = None
    except LookupError as e:
        initiator_practitioner_role = None
        logger.error(str(e))
        missing_resources.append("Initiator PractitionerRole")

    try:
        recipient_practitioner_role = parser.find_resource_by_profile(request_bundle, recipient_practitioner_role_profile)
        recipient_practitioner_role = PractitionerRole(**parser.simplify_references(recipient_practitioner_role))
        # Strip the Endpoint and Healthcare Services for now for simplicity. No need to echo them back.
        # TODO: Generalize this for non BSeR Engine created bundles.
        recipient_practitioner_role.healthcareService = None
        recipient_practitioner_role.endpoint = None
    except LookupError as e:
        recipient_practitioner_role = None
        logger.error(str(e))
        missing_resources.append("Recipient PractitionerRole")

    # Get all references from the PractitionerRole resources and add to list.
    initiator_resource_references = parser.get_references(initiator_practitioner_role, [])
    initiator_resources = []
    for reference in initiator_resource_references:
        initiator_resources.append(parser.find_resource_by_reference(request_bundle, reference))

    recipient_resource_references = parser.get_references(recipient_practitioner_role, [])
    recipient_resources = []
    for reference in recipient_resource_references:
        recipient_resources.append(parser.find_resource_by_reference(request_bundle, reference))
    

    if missing_resources:
        # Return Operation Outcome
        return oobuilder.build_missing_resource_operation_outcome(missing_resources)
    else:
        # Modify Task Status
        try:
            task = set_task_status(task, action)
        except ValueError as e:
            return oobuilder.build_action_error_operation_outcome(str(e))

        # Build the New Bundle
        message_bundle = build_bser_message_bundle()
        message_header = build_bser_message_header(
            request_bundle.entry[0].resource,
            create_reference(task),
            create_reference(initiator_practitioner_role),
            create_reference(recipient_practitioner_role))
        message_bundle = insert_message_header(message_bundle, message_header)
        message_bundle = append_entry(message_bundle, task)
        message_bundle = append_entry(message_bundle, service_request)
        message_bundle = append_entry(message_bundle, patient)
        message_bundle = append_entry(message_bundle, initiator_practitioner_role)

        if status_message:
            referral_activity_status = build_referral_activity_status(status_message, patient)
            message_bundle = append_entry(message_bundle, referral_activity_status)

        for resource in initiator_resources:
            message_bundle = append_entry(message_bundle, resource)
        message_bundle = append_entry(message_bundle, recipient_practitioner_role)
        for resource in recipient_resources:
            message_bundle = append_entry(message_bundle, resource)
        return message_bundle

def set_task_status(task: Task, action: str):
    if action.lower() == "accept".lower():
        business_status = {
                "coding": [{
                    "system": "http://hl7.org/fhir/us/bser/CodeSystem/TaskBusinessStatusCS",
                    "code": "3.0",
                    "display": "Service Request Accepted"
                }]
            }
        business_status = CodeableConcept(**business_status)
    elif action.lower() == "decline".lower():
        business_status = {
                "coding": [{
                    "system": "http://hl7.org/fhir/us/bser/CodeSystem/TaskBusinessStatusCS",
                    "code": "4.0",
                    "display": "Service Request Declined"
                }]
            }
        business_status = CodeableConcept(**business_status)
    elif action.lower() == "updateprogress".lower():
        # TODO: Maintainence issue with IG, update to granular codes once/if available.
        business_status = {
                "coding": [{
                    "system": "http://hl7.org/fhir/us/bser/CodeSystem/TaskBusinessStatusCS",
                    "code": "5.x",
                    "display": "Service Request Event State Change"
                }]
            }
        business_status = CodeableConcept(**business_status)
    elif action.lower() == "cancel".lower():
        business_status = {
                "coding": [{
                    "system": "http://hl7.org/fhir/us/bser/CodeSystem/TaskBusinessStatusCS",
                    "code": "6.0",
                    "display": "Service Request Fulfillment Cancelled"
                }]
            }
        business_status = CodeableConcept(**business_status)
    else:
        raise ValueError(f"{action} is not a supported action. Currently supported: {', '.join(currently_supported_actions)}")
    task.businessStatus = business_status
    return task

# TODO: Replace with fhir.bser once available.
def build_bser_message_bundle():
    profile_url = "http://hl7.org/fhir/us/bser/StructureDefinition/BSeR-ReferralMessageBundle"
    bundle = {}
    bundle["resourceType"] = "Bundle"
    bundle['meta'] = {"profile": [profile_url]}
    bundle['type'] = "message"
    bundle = Bundle(**bundle)
    return bundle

# TODO: Replace with fhir.bser once available.
def build_bser_message_header(initiator_message_header: MessageHeader, task_reference, initiator_reference, recipient_reference):
    profile_url = "http://hl7.org/fhir/us/bser/StructureDefinition/BSeR-ReferralMessageHeader"
    initiator_endpoint = initiator_message_header.source.endpoint
    recipient_endpoint = initiator_message_header.destination[0].endpoint
    message_header = {}
    message_header["resourceType"] = "MessageHeader"
    message_header["meta"] = {"profile": [profile_url]}
    message_header["id"] = str(uuid.uuid4())
    message_header["eventCoding"] = {
          "system": "http://terminology.hl7.org/CodeSystem/v2-0003",
          "code": "I12",
          "display": "REF/RRI - Patient referral"
        }
    
    # Swap Initiator and Recipient Information due to feedback directionality.
    message_header["destination"] = [{
        "endpoint": initiator_endpoint,
        "receiver": initiator_reference
    }]
    message_header["sender"] = recipient_reference
    message_header["source"] = {
          "endpoint": recipient_endpoint
        }
    message_header["focus"] = [task_reference]
    message_header = MessageHeader(**message_header)
    return message_header

# TODO: Replace with fhir.bser once available.
def build_referral_activity_status(status_message: str, patient: Patient):
    profile_url = "http://hl7.org/fhir/us/bser/StructureDefinition/BSeR-ReferralActivityStatus"
    referral_activity_status = {}
    referral_activity_status["resourceType"] = "Observation"
    referral_activity_status["meta"] = {"profile": [profile_url]}
    referral_activity_status["id"] = str(uuid.uuid4())
    referral_activity_status["status"] = "final"
    referral_activity_status["code"] = {
        "coding": [{"system" : "http://snomed.info/sct", "code" : "385641008", "display" : "Action status"}]
    }
    referral_activity_status["subject"] = create_reference(patient)
    referral_activity_status["valueString"] = status_message

    referral_activity_status = Observation(**referral_activity_status)
    
    return referral_activity_status

def create_reference(resource):
    resource_type = resource.resource_type
    resource_id = resource.id
    reference = {"reference": f"{resource_type}/{resource_id}"}
    return reference

# TODO: Figure out how to work with the list operations directly on the bundle with fhir.resources.
def insert_message_header(message_bundle: Bundle, message_header: MessageHeader):
    message_bundle_entry_list = message_bundle.entry
    if message_bundle_entry_list is None:
        message_bundle_entry_list = []
    bundle_entry = BundleEntry()
    bundle_entry.fullUrl = f"{message_header.resource_type}/{message_header.id}"
    bundle_entry.resource = message_header
    message_bundle_entry_list.insert(0, bundle_entry)
    message_bundle.entry = message_bundle_entry_list
    return message_bundle

# TODO: Figure out how to work with the list operations directly on the bundle with fhir.resources.
def append_entry(message_bundle: Bundle, resource):
    message_bundle_entry_list = message_bundle.entry
    if message_bundle_entry_list is None:
        message_bundle_entry_list = []
    bundle_entry = BundleEntry()
    bundle_entry.fullUrl = f"{resource.resource_type}/{resource.id}"
    bundle_entry.resource = resource
    message_bundle_entry_list.append(bundle_entry)
    message_bundle.entry = message_bundle_entry_list
    return message_bundle