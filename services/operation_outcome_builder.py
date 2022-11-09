from fhir.resources.operationoutcome import OperationOutcome


# TODO: Change to more natural fhir.resources pattern, don't have time to figure out right now. 11/8/22.
def build_missing_resource_operation_outcome(missing_resources: list):
    operation_outcome = {
        "resourceType": "OperationOutcome",
        "issue": [
            {
                "severity": "error",
                "code": "invalid",
                "details": {
                    "text": f"Invalid BSeR Referral Message Bundle. Missing following resources: {', '.join(missing_resources)}."
                }
            }
        ]
    }
    operation_outcome = OperationOutcome(**operation_outcome)
    return operation_outcome

def build_action_error_operation_outcome(error: str):
    operation_outcome = {
        "resourceType": "OperationOutcome",
        "issue": [
            {
                "severity": "error",
                "code": "value",
                "details": {
                    "text": error
                }
            }
        ]
    }
    operation_outcome = OperationOutcome(**operation_outcome)
    return operation_outcome