from typing import List, Dict

from sftools_service.domain.enums.recipe_type import RecipeType
from sftools_service.domain.models.building import Building
from sftools_service.domain.models.item import Item


class Recipe:
    def __init__(self,
                 name: str,
                 building: Building,
                 output1_item: Item,
                 output1_rate: float,
                 output1_stack: int,
                 output2_item: Item = None,
                 output2_rate: float = None,
                 output2_stack: int = None,
                 ingredient1_item: Item = None,
                 ingredient1_rate: float = None,
                 ingredient1_stack: int = None,
                 ingredient2_item: Item = None,
                 ingredient2_rate: float = None,
                 ingredient2_stack: int = None,
                 ingredient3_item: Item = None,
                 ingredient3_rate: float = None,
                 ingredient3_stack: int = None,
                 ingredient4_item: Item = None,
                 ingredient4_rate: float = None,
                 ingredient4_stack: int = None,
                 ):
        self._name = name
        self._building = building
        self._output1_item = output1_item
        self._output1_rate = output1_rate
        self._output1_stack = output1_stack
        self._output2_item = output2_item
        self._output2_rate = output2_rate
        self._output2_stack = output2_stack
        self._ingredient1_item = ingredient1_item
        self._ingredient1_rate = ingredient1_rate
        self._ingredient1_stack = ingredient1_stack
        self._ingredient2_item = ingredient2_item
        self._ingredient2_rate = ingredient2_rate
        self._ingredient2_stack = ingredient2_stack
        self._ingredient3_item = ingredient3_item
        self._ingredient3_rate = ingredient3_rate
        self._ingredient3_stack = ingredient3_stack
        self._ingredient4_item = ingredient4_item
        self._ingredient4_rate = ingredient4_rate
        self._ingredient4_stack = ingredient4_stack

        self._type = RecipeType.ALTERNATE if self._name.count('Alternate') else RecipeType.BASIC

    @property
    def name(self):
        return self._name

    @property
    def type(self):
        return self._type

    @property
    def building(self):
        return self._building

    @property
    def output_item(self):
        if self._name.count(self._output1_item.name):
            return self._output1_item
        else:
            return self._output2_item

    @property
    def output_rate(self):
        if self._name.count(self._output1_item.name):
            return self._output1_rate
        else:
            return self._output2_rate
        
    @property
    def sink_item(self):
        if not self.output2_item:
            return None
        if self._name.count(self._output1_item.name):
            return self._output2_item
        else:
            return self._output1_item

    @property
    def sink_rate(self):
        if not self.output2_item:
            return None
        if self._name.count(self._output1_item.name):
            return self._output2_rate
        else:
            return self._output1_rate

    # def generate_demands(self, depth: int, scaler: float = 1.0) -> List[Demand]:
    #     demands = []
    #     if self._ingredient1_item:
    #         demands.append(Demand(self._ingredient1_item.name, self._ingredient1_item, self._ingredient1_rate * scaler, DemandType.PRODUCE, depth))
    #     if self._ingredient2_item:
    #         demands.append(Demand(self._ingredient2_item.name, self._ingredient2_item, self._ingredient2_rate * scaler, DemandType.PRODUCE, depth))
    #     if self._ingredient3_item:
    #         demands.append(Demand(self._ingredient3_item.name, self._ingredient3_item, self._ingredient3_rate * scaler, DemandType.PRODUCE, depth))
    #     if self._ingredient4_item:
    #         demands.append(Demand(self._ingredient4_item.name, self._ingredient4_item, self._ingredient4_rate * scaler, DemandType.PRODUCE, depth))
    #     if self.sink_item:
    #         demands.append(Demand(self.sink_item.name, self.sink_item, self.sink_rate * scaler, DemandType.SINK, depth))
    #
    #     return demands

    # ----------------------------------------------------------------------------------------------------------------

    @property
    def output1_item(self):
        return self._output1_item

    @property
    def output1_rate(self):
        return self._output1_rate

    @property
    def output1_stack(self):
        return self._output1_stack

    @property
    def output2_item(self):
        return self._output2_item

    @property
    def output2_rate(self):
        return self._output2_rate

    @property
    def output2_stack(self):
        return self._output2_stack

    @property
    def ingredient1_item(self):
        return self._ingredient1_item

    @property
    def ingredient1_rate(self):
        return self._ingredient1_rate

    @property
    def ingredient1_stack(self):
        return self._ingredient1_stack

    @property
    def ingredient2_item(self):
        return self._ingredient2_item

    @property
    def ingredient2_rate(self):
        return self._ingredient2_rate

    @property
    def ingredient2_stack(self):
        return self._ingredient2_stack

    @property
    def ingredient3_item(self):
        return self._ingredient3_item

    @property
    def ingredient3_rate(self):
        return self._ingredient3_rate

    @property
    def ingredient3_stack(self):
        return self._ingredient3_stack

    @property
    def ingredient4_item(self):
        return self._ingredient4_item

    @property
    def ingredient4_rate(self):
        return self._ingredient4_rate

    @property
    def ingredient4_stack(self):
        return self._ingredient4_stack

    @property
    def ingredients(self) -> List[Item]:
        return [item for item in [self._ingredient1_item, self._ingredient2_item, self._ingredient3_item, self._ingredient4_item,] if item]

    @property
    def ingredient_rates_by_ingredient_name(self) -> Dict[str, float]:
        rates = {}
        if self._ingredient1_item:
            rates[self._ingredient1_item.name] = self.ingredient1_rate
        if self._ingredient2_item:
            rates[self._ingredient2_item.name] = self.ingredient2_rate
        if self._ingredient3_item:
            rates[self._ingredient3_item.name] = self.ingredient3_rate
        if self._ingredient4_item:
            rates[self._ingredient4_item.name] = self.ingredient4_rate
        return {item.name: rates[item.name] for item in [self._ingredient1_item, self._ingredient2_item, self._ingredient3_item, self._ingredient4_item,] if item}

    def __repr_ingredients(self):
        result = ''
        if self._ingredient1_item:
            result += self._ingredient1_item.name + '[' + str(self._ingredient1_rate) + ']'

        if self._ingredient2_item:
            result += ' & ' + self._ingredient2_item.name + '[' + str(self._ingredient2_rate) + ']'

        if self._ingredient3_item:
            result += ' & ' + self._ingredient3_item.name + '[' + str(self._ingredient3_rate) + ']'

        if self._ingredient4_item:
            result += ' & ' + self._ingredient4_item.name + '[' + str(self._ingredient4_rate) + ']'

        if self.sink_item:
            result += ' >>> ' + self.sink_item.name + '[' + str(self.sink_rate) + ']'

        return result

    def __repr__(self):
        return self._name + ' <<< ' + self.__repr_ingredients()
