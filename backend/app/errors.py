##..

class ApiError(Exception): #custom exception
    def __init__(self, status, message, details=None):
        super().__init__(message) #call the  parent?
        self.status = status # http code?
        self.message = message 
        self.details = details #and field errors
