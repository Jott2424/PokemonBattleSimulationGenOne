class Move:
    def __init__(self, move_details: dict):
        self.id = move_details['fk_moves_id']
        self.name = move_details['move']
        self.type = move_details['type']
        self.type_id = move_details['fk_types_id']
        self.power = move_details['power']
        self.accuracy = move_details['accuracy']
        self.damagecategory = move_details['damagecategory']
        self.damagecategory_id = move_details['mdc_id']

        self.pp_start = move_details['pp']
        self.pp_curr = move_details['pp']

#just for printing
    def __repr__(self):
        attrs = ', '.join(f"{k}={v!r}" for k, v in vars(self).items())
        return f"{self.__class__.__name__}({attrs})"