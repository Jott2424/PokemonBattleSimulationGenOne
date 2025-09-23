class Move:
    def __init__(self, move_details: dict):
        self.id = move_details['id']
        self.name = move_details['name']
        self.type = move_details['type']
        self.power = move_details['power']
        self.typeId = move_details['typeId']
        self.accuracy = move_details['accuracy']
        self.damagecategory = move_details['damagecategory']

        self.pp_start = move_details['powerpoints']
        self.pp_curr = move_details['powerpoints']

#just for printing
    def __repr__(self):
        attrs = ', '.join(f"{k}={v!r}" for k, v in vars(self).items())
        return f"{self.__class__.__name__}({attrs})"