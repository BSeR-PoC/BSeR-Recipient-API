import logging
from fhir.resources.bundle import Bundle
from fhir.resources.reference import Reference
from fhir.resources.patient import Patient
from fhir.resources.practitionerrole import PractitionerRole
from fhir.resources.servicerequest import ServiceRequest
from collections import OrderedDict

logger = logging.getLogger('bserfeedbackapi.util.bundleparser')

def find_subject(bundle: Bundle, service_request: ServiceRequest):
    try:
        patient_reference = service_request.subject.reference
    except Exception:
        raise LookupError(f"Failed finding ServiceRequest.subject reference. This is likely due to a missing ServiceRequest, and may not indicate an issue with the Patient directly.")

    try:    
        patient = find_resource_by_reference(bundle, patient_reference)
    except LookupError as e:
        raise e
    
    return patient

def find_resource_by_profile(bundle: Bundle, profile: str):
    for entry in bundle.entry:
        try:
            if profile in entry.resource.meta.profile:
                return entry.resource
        except Exception:
            logger.debug(f"Bundle entry {entry.fullUrl} does not have profile.")
    raise LookupError(f"Resource with profile {profile} not found.")

def find_resource_by_id(bundle: Bundle, id: str):
    for entry in bundle.entry:
        if entry.resource.id == id:
            return entry.resource
    raise LookupError(f"Resource with id {id} not found.")

def find_resource_by_reference(bundle: Bundle, reference: Reference):
    for entry in bundle.entry:
        if entry.fullUrl == reference or reference.endswith(entry.fullUrl):
            return entry.resource
        elif f"{entry.resource.resource_type}/{entry.resource.id}" == reference:
            return entry.resource
    raise LookupError(f"Resource with reference {reference} not found.")

def get_references(resource, reference_list: list):
    if type(resource) is not OrderedDict:
        resource = resource.dict(exclude_none=True)
    for k, v in resource.items():
        if k == "reference":
            reference_list.append(resource[k])
        elif type(v) is list:
            for item in v:
                if type(item) is OrderedDict:
                    get_references(item, reference_list)
        elif type(v) is OrderedDict:
            get_references(v, reference_list)
    return reference_list

def simplify_references(resource):
    if type(resource) is not OrderedDict:
        resource = resource.dict(exclude_none=True)
    for k, v in resource.items():
        if k == "reference":
            resource[k] = clean_reference_url(v)
        elif type(v) is list:
            for item in v:
                if type(item) is OrderedDict:
                    simplify_references(item)
        elif type(v) is OrderedDict:
            simplify_references(v)
    return resource

def clean_reference_url(reference: str):
    split_string = reference.split("/")[-2:]
    recombined_string = f"{split_string[-2]}/{split_string[-1]}"
    return recombined_string