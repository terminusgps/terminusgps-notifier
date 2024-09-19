import requests
import datetime

def main() -> None:
    data = {
        "to_number": "+17133049421",
        "message": f"This is a test at '{datetime.datetime.now()}'!"
    }
    response = requests.post("http://localhost:8000/notify/call", data=data)
    if not response.status_code == 200:
        print(response)
        raise Exception

if __name__ == "__main__":
    main()
