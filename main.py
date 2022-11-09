from fastapi import FastAPI
from fhir.resources.bundle import Bundle
from util.formatter import CustomFormatter
import logging
from fastapi.middleware.cors import CORSMiddleware
from services.feedback_bundle_builder import create_feedback

logger = logging.getLogger('bserfeedbackapi')
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(CustomFormatter())
logger.addHandler(ch)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "API Root. Please visit /docs for the Swagger Documentation."}


@app.post("/generate")
def generate_feedback(bundle: Bundle, action: str):
    logger.info(f"Received request to generate Feedback Bundle with Action: {action}")

    # If error, returns OperationOutcome. Otherwise returns Message Bundle.
    outcome = create_feedback(bundle, action)
    return outcome.dict()