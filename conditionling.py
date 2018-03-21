# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

import os
import operator
from textx.metamodel import metamodel_from_file

file = "conditionling.tx"
path = os.path.dirname(os.path.realpath(__file__))
conditionling_metamodel = metamodel_from_file(os.path.join(path, file))

def evaluate_conditions(dsl_string, environment):
    conditions = conditionling_metamodel.model_from_str(dsl_string)

    evaluated = []
    for condition in conditions.conditions:
        evaluated.append(evaluate_condition(condition, environment))

    if all_true(evaluated):
        return True
    else:
        return False

def evaluate_condition(condition, environment):

    operator_lookup = {
        "<" : operator.lt,
        "<=" : operator.le,
        "==" : operator.eq,
        "!=" : operator.ne,
        ">=" : operator.ge,
        ">" : operator.gt
    }

    if condition.field in environment:
        field_value = environment[condition.field]
        if condition.left_compare:
            left_result = operator_lookup[condition.left_compare.comparator_symbol.symbol](condition.left_compare.comparator_value, field_value)
        else:
            left_result = None

        if condition.right_compare:
            right_result = operator_lookup[condition.right_compare.comparator_symbol.symbol](field_value, condition.right_compare.comparator_value)
        else:
            right_result = None

        results = [s for s in [left_result, right_result] if s is not None]

        if all_true(results):
            return True
        else:
            return False
    else:
        return False

def all_true(values):
    if len(set(values)) == 1 and True in set(values):
        return True
    else:
        return False

def test():
    dsl_string = "width > 5.0 in\n4.0 in < height > 50.0 in"
    print(evaluate_conditions(dsl_string, {"height" : 10, "width" : 6}))