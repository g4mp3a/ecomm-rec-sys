from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any

import numpy as np
import weaviate
from weaviate.util import get_valid_uuid
from uuid import uuid4

from backend.queries import (populate_query, get_prod_uuid,
                             get_user_vector_and_clicks,
                             searchbar_query)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_weaviate_client():
    return weaviate.Client("http://localhost:8080")

def create_uuid():
    return get_valid_uuid(uuid4())

client = get_weaviate_client()
user_id = create_uuid()

def start_new_user_session():
    data_properties = {"sessionNumber": 0}
    client.data_object.create(data_properties, "User", user_id)
    return user_id
start_new_user_session()

@app.get("/", response_class=HTMLResponse)
async def read_item(request: Request) -> templates.TemplateResponse:
    """
    Handle GET requests to the root URL.
    Args:
    - request (Request): The request object.
    Returns:
    - templates.TemplateResponse: The HTML response.
    """
    random_vector = np.random.rand(512)
    data = populate_query(random_vector, client)
    context = {"request": request, "data": data}
    return templates.TemplateResponse("index.html", context=context)

@app.post("/image-clicked")
async def image_clicked(data: Dict[str, Any], request: Request) -> Dict[str, Any]:
    """
    Handle the event when a user clicks on an image.
    If the image was previously un-clicked, it is marked as clicked, and vice versa.
    """
    image_path = data.get("imagePath")
    query_label = image_path.replace("images/", "").replace(".jpg", "")
    product_uuid = get_prod_uuid(query_label, client)
    _, user_clicks = get_user_vector_and_clicks(user_id, client)
    # Handle the case when the image is already clicked by the user
    if image_path in user_clicks:
        # User un-clicked the image
        # Delete the cross-reference
        client.data_object.reference.delete(
            from_uuid=user_id,
            from_property_name="likedItem",
            to_uuid=product_uuid
        )
    else:
        # User clicked the image
        # Add new cross-reference
        client.data_object.reference.add(
            from_uuid=user_id,
            from_property_name="likedItem",
            to_uuid=product_uuid
        )

    user_vector, user_clicks = get_user_vector_and_clicks(user_id, client)
    # If user vector is empty, make up a vector for the fake user
    if len(user_vector) < 1:
        user_vector = np.random.rand(512,)

    data = populate_query(user_vector, client)

    return {
        "data": data,
        "user_clicks": user_clicks
    }

@app.post("/text-search")
async def text_search(data: Dict[str, Any], request: Request) -> Dict[str, Any]:
    """
    Endpoint for performing a text search.

    Args:
    - data: A dictionary containing the search query.
    - request: The FastAPI request object.

    Returns:
    - A dictionary containing the search results and user clicks.
    """
    # Extract the search query from the data dictionary
    text_query = data.get("searchQuery")

    # Get the user vector and clicks
    _, user_clicks = get_user_vector_and_clicks(user_id, client)

    # Perform the search bar query
    data = searchbar_query(text_query, user_id, user_clicks, client)

    # Prepare the return dictionary
    return {
        "data": data,
        "user_clicks": user_clicks
    }
