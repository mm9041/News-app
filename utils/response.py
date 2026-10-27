from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


def success_response(message: str = "success", data=None):
    content = {
        "code": 200,
        "message": message,
        "data": data
    }
    return JSONResponse(content=jsonable_encoder(content))


def error_response(message: str = "error", data=None):
    content = {
        "code": 500,
        "message": message,
        "data": data
    }
    return JSONResponse(content=jsonable_encoder(content))
