#!/usr/bin/env python
import os.path
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from datetime import timedelta

from app.utils.security import create_jwt_token

if __name__ == "__main__":
    access_token_expires = timedelta(days=1)
    encoded_jwt = create_jwt_token(
        data={"sub": "antoine"}, expires_delta=access_token_expires
    )

    print(encoded_jwt)
