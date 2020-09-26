import re
from DataStructure import *

def num(s):
    try:
        return int(s)
    except ValueError:
        return float(s)


def find_the_correct_space(target_str):
    get_index = target_str.find('getelementptr')
    if get_index != -1:
        return get_index - 1
    start_index = 0
    space_index = -1
    while start_index < len(target_str):
        if target_str[start_index] == ' ':
            space_index = start_index
        start_index += 1
    return space_index


def detect_if_is_syncthreads(statement):
    return statement.find("call void @__syncthreads()") != -1


def is_memory(data_type):
    if data_type.value is None:
        return False
    try:
        return data_type.value[0] == '%' or data_type.value[0] == '@'
    except:
        return False


def is_global_memory(data_type):
    try:
        return data_type.value[0] == '%'
    except:
        return False

def parse_arguments(target_args):
    result = list()
    # todo: parse argument string list ['(type token)|command', ...]
    start_index = 0
    tmp_result = ''
    while start_index != len(target_args):
        if target_args[start_index] == '(':
            tmp_result += target_args[start_index]
            start_param = 1
            start_index += 1
            while start_param != 0:
                tmp_result += target_args[start_index]
                if target_args[start_index] == '(':
                    start_param += 1
                elif target_args[start_index] == ')':
                    start_param -= 1
                start_index += 1
        elif target_args[start_index] == ',':
            result.append(tmp_result)
            tmp_result = ''
            start_index += 1
        else:
            tmp_result += target_args[start_index]
            start_index += 1
    result.append(tmp_result)
    for index in xrange(len(result)):
        element_index = result[index].find('getelementptr')
        if element_index != -1:
            result[index] = result[index][element_index:]
    return result

class Executor:
    def __init__(self, kernel_codes, main_memory, global_env, local_env):
        self.kernel_codes = kernel_codes
        self.main_memory = main_memory
        self.global_env = global_env
        self.local_env = local_env

    def on_alloca(self, arguments):
        arguments = arguments.split(', align')
        type_name = arguments[0].strip()
        new_type = DataType(type_name)
        if type_name.find("{") != -1:
            new_type_name = type_name[1: len(type_name) - 1]
            new_type_lst = new_type_name.split(",")
            new_type_lst = [DataType(item.strip()) for item in new_type_lst]
            new_type.set_value(new_type_lst)
        return new_type, None, None, None

    def is_target_memory(self, data_type):
        if data_type.value == self.main_memory['global']:
            return True
        if data_type.value == self.main_memory['shared']:
            return True  # is shared memory
        return False

    # 2 type: struct, memory index, return value has two kinds: one is actually value of struct, the other is memory index
    def on_getelementptr(self, arguments):
        arguments = arguments.strip()
        local_arguments = arguments.replace("inbounds", "")
        local_arguments = local_arguments.replace("(", "")
        local_arguments = local_arguments.replace(")", "")
        local_arguments = local_arguments.split(",")
        target = self._execute_item(local_arguments[0])
        local_arguments = [item for item in local_arguments if item.find('!dbg') == -1 and item.find('align') == -1]
        tmp_index = self._execute_item(local_arguments[-1])
        if is_memory(target):
            result_tmp = DataType('memory-index')
            result_tmp.set_is_getelementptr(True)
            if target.memory_index is not None and not tmp_index.is_depend_on_running_time:
                result_tmp.set_memory_index(num(tmp_index.get_value()) + num(target.memory_index))
            elif not tmp_index.is_depend_on_running_time:
                try:
                    result_tmp.set_memory_index(num(tmp_index.get_value()))
                except:
                    result_tmp.set_memory_index(0)  # initialized load a new shared memory
            else:
                result_tmp.set_memory_index(None)
            result_tmp.set_value(target.get_value())
            return result_tmp, None, None, None
        else:
            return target.get_value()[num(tmp_index.get_value())], None, None, None


    # todo
    # need distinguish target is a register or memory
    def on_store(self, arguments):
        arguments = arguments.strip()
        arguments = parse_arguments(arguments)
        source = self._execute_command(arguments[0])[0]
        target = self._execute_command(arguments[1])[0]
        if self.is_target_memory(target) and target.memory_index is not None and target.is_getelementptr is True:
            if arguments[1].find("**") == -1:
                target_memory = self.global_env.get_value("memory_container")
                if target_memory.has_target_memory(target.value):
                    target_memory.add_value_to_memory(target, source)
                return source, "write", target.memory_index, is_global_memory(target)
            return source, None, None, None
        else:
            var_lst = arguments[1].strip()
            var_lst = var_lst.split(' ')
            if var_lst[1][0] == '@':
                self.global_env.add_value(var_lst[1], source)
            else:
                self.local_env.add_value(var_lst[1], source)
            return source, None, None, None


    # todo
    # need distinguish result is a register or memory
    def on_load(self, arguments):
        arguments = arguments.strip()
        split_index = arguments.find(' ')
        target_command = arguments[split_index + 1:]
        target_type = arguments[: split_index]
        if target_command.find('getelementptr') != -1:
            result = self._execute_command(arguments[split_index + 1:])[0]
        else:
            result = self._execute_item(target_command.split(',')[0])
        if self.is_target_memory(result) and result.memory_index is not None and result.is_getelementptr is True \
                and result.is_depend_on_running_time is False:  # haven't been loaded to register
            result.set_is_depend_on_running_time(True)
            if target_type.find("**") == -1:
                result_tmp = None
                target_memory = self.global_env.get_value("memory_container")
                if target_memory.has_target_memory(result.value):
                    result_tmp = target_memory.get_value_from_memory(result)
                if result_tmp is None:
                    result_tmp = DataType(target_type[: len(target_type) - 1])
                    result_tmp.set_is_depend_on_running_time(True)
                return result_tmp, "read", result.memory_index, is_global_memory(result)
            return result, None, None, None
        # load data instead of address (data is one type, address is another type)
        if is_memory(result) and target_type.find("**") == -1:
            result_tmp = None
            result.set_is_depend_on_running_time(True)
            target_memory = self.global_env.get_value("memory_container")
            if target_memory.has_target_memory(result.value):
                result_tmp = target_memory.get_value_from_memory(result)
            if result_tmp is None:
                result_tmp = DataType(target_type[: len(target_type) - 1])
                result_tmp.set_is_depend_on_running_time(True)
            return result_tmp, None, None, None
        return result, None, None, None



    def on_call(self, arguments):
        arguments = arguments.strip()
        split_index = arguments.find(' ')
        target_function_pattern = r".*?(?P<function_name>[@][^(]+)\((?P<argus>.*)\)"
        target_function_pattern = re.compile(target_function_pattern, re.DOTALL)
        arguments = arguments[split_index + 1:]
        matcher = target_function_pattern.search(arguments)
        target_function = self.global_env.get_value(matcher.group('function_name'))
        if target_function is None:
            return None, None, None, None
        argus_value = matcher.group('argus')
        argus_value = parse_arguments(argus_value)
        argus_value = [self._execute_command(single_value)[0]
                    for single_value in argus_value]
        argus_dict = dict()
        value_index = 0
        for key in target_function.argument_lst:
            argus_dict[key] = argus_value[value_index]
            value_index += 1
        self.kernel_codes.prepared_launch_function(self.local_env, KernelCodes(target_function.raw_codes), argus_dict, self.local_env.get_value("current_stmt"))
        return None, None, None, None


    def on_ret(self, arguments):
        if arguments.find('void') != -1:
            self.kernel_codes.restore_after_execution_function(self.local_env)
            return None, None, None, None
        else:
            arguments = arguments.strip()
            arguments = arguments.split(',')[0]
            split_index = arguments.find(' ')
            arguments = arguments[split_index + 1:].strip()
            result = self._execute_item(arguments)
            self.kernel_codes.set_return_value(result)
            self.kernel_codes.restore_after_execution_function(self.local_env)
            return result, None, None, None


    def on_icmp(self, arguments):
        result_tmp = DataType('i1')
        oper_dict = {
            'eq': lambda x, y: x == y,
            'ne': lambda x, y: x != y,
            'gt': lambda x, y: x > y,
            'ge': lambda x, y: x >= y,
            'lt': lambda x, y: x < y,
            'le': lambda x, y: x <= y,
        }
        arguments = arguments.strip()
        split_index = arguments.find(' ')
        operator, actual_arguments = arguments[: split_index], arguments[split_index + 1:]
        if len(operator) > 2:
            operator = operator[1:]
        split_index = actual_arguments.find(' ')
        actual_arguments = actual_arguments[split_index + 1:]
        actual_arguments = actual_arguments.split(',')
        number_one = self._execute_item(actual_arguments[0])
        number_two = self._execute_item(actual_arguments[1])
        if number_two.is_depend_on_running_time or number_one.is_depend_on_running_time:
            result_tmp.set_is_depend_on_running_time(True)
        else:
            result_tmp.set_value(oper_dict[operator](num(number_one.get_value()), num(number_two.get_value())))
        return result_tmp, None, None, None

    on_fcmp = on_icmp


    def on_br(self, arguments):
        arguments = arguments.strip()
        split_index = arguments.find(' ')
        if arguments[:split_index].find('label') != -1:
            new_line = arguments[split_index + 1:].split(',')[0]
            new_line = new_line[1:]
            self.kernel_codes.set_next_statement(self.kernel_codes.get_label_by_mark(new_line))
        else:
            new_line = arguments[split_index + 1:].strip()
            new_line = new_line.split(',')
            bool_res = self._execute_item(new_line[0])
            if_true = new_line[1][new_line[1].find('%') + 1:]
            if_false = new_line[2][new_line[2].find('%') + 1:]
            if bool_res.is_depend_on_running_time:
                current_stmt = self.kernel_codes.get_current_statement()
                if self.kernel_codes.is_already_here(current_stmt):
                    self.kernel_codes.set_next_statement(self.kernel_codes.get_label_by_mark(if_false))
                else:
                    self.kernel_codes.add_current_stmt_to_depending_branch(current_stmt)
                    self.kernel_codes.set_next_statement(self.kernel_codes.get_label_by_mark(if_true))
            elif bool(bool_res.get_value()):
                self.kernel_codes.set_next_statement(self.kernel_codes.get_label_by_mark(if_true))
            else:
                self.kernel_codes.set_next_statement(self.kernel_codes.get_label_by_mark(if_false))
        return None, None, None, None


    def on_phi(self, arguments):
        arguments = arguments.strip()
        split_index = arguments.find(' ')
        should_handle = arguments[split_index + 1:].strip()
        argus_pattern = r"\[\s*(?P<value1>[^\s]+),\s*(?P<label1>[^\s]+)\s*\],\s*\[\s*(?P<value2>[^\s]+),\s*(?P<label2>[^\s]+)\s*\]"
        argus_pattern = re.compile(argus_pattern)
        matcher = argus_pattern.search(should_handle)
        recent_label = '%' + self.kernel_codes.get_recently_label()
        if recent_label == matcher.group("label1"):
            return self._execute_command(matcher.group("value1"))
        else:
            return self._execute_command(matcher.group("value2"))


    def on_select(self, arguments):
        arguments = arguments.strip()
        condition, value_one, value_two = arguments.split(',')[: 3]
        condition_value = self._execute_item(condition)
        value_one_real = self._execute_item(value_one)
        value_two_real = self._execute_item(value_two)
        if condition_value.is_depend_on_running_time:
            result_tmp = DataType(value_one_real.get_type())
            result_tmp.set_is_depend_on_running_time(True)
            return result_tmp, None, None, None
        if condition_value.get_value():
            return value_one_real, None, None, None
        return value_two_real, None, None, None

    def calculation_factory(cac_flag):
        #  cac_flag = 0 -> +, 1 -> -, 2 -> *, 3 -> \, 4 -> %, 5 -> >>, 6 -> &, 7 -> <<
        def __cal(self, arguments):
            arguments = arguments.replace("nsw", "")
            arguments = arguments.strip()
            arguments = arguments.split(',')
            var_lst = arguments[0].strip().split(' ')
            tmp_result = DataType(var_lst[0].strip())
            number_one = self._execute_item(var_lst[1].strip())
            number_two = self._execute_item(arguments[1])
            if number_one.is_depend_on_running_time or number_two.is_depend_on_running_time:
                tmp_result.set_is_depend_on_running_time(True)
                return tmp_result, None, None, None
            if cac_flag == 0:
                tmp_result.set_value(num(number_one.get_value()) + num(number_two.get_value()))
            elif cac_flag == 1:
                tmp_result.set_value(num(number_one.get_value()) - num(number_two.get_value()))
            elif cac_flag == 2:
                tmp_result.set_value(num(number_one.get_value()) * num(number_two.get_value()))
            elif cac_flag == 3:
                if num(number_two.get_value()) == 0:
                    tmp_result.set_value(0)  # divide 0
                else:
                    tmp_result.set_value(num(number_one.get_value()) / num(number_two.get_value()))
            elif cac_flag == 4:
                if num(number_two.get_value()) == 0:
                    tmp_result.set_value(0)
                else:
                    tmp_result.set_value(num(number_one.get_value()) % num(number_two.get_value()))
            elif cac_flag == 5:
                tmp_result.set_value(num(number_one.get_value()) >> num(number_two.get_value()))
            elif cac_flag == 6:
                if tmp_result.data_type == 'i1':
                    if number_one.get_value() is None or number_two.get_value() is None:  # no execute no true
                        tmp_result.set_value(False)
                    else:
                        tmp_result.set_value(number_one.get_value() and number_two.get_value())
                else:
                    tmp_result.set_value(num(number_one.get_value()) & num(number_two.get_value()))
            elif cac_flag == 7:
                tmp_result.set_value(num(number_one.get_value()) << num(number_two.get_value()))
            return tmp_result, None, None, None
        return __cal


    def single_elem_calculation_factory(cac_flag):
        #  cal_flag: 0->sext, bitcast, sitofp
        def __cal(self, arguments):
            arguments = arguments.strip()
            arguments = arguments.split(' ')
            old_data = self._execute_item(arguments[1])
            new_data = DataType('..')
            old_data.copy_and_replace(new_data)
            new_data.set_type(arguments[3])
            return new_data, None, None, None
        return __cal

    on_fadd = on_add = calculation_factory(0)
    on_sub = on_fsub = calculation_factory(1)
    on_mul = on_fmul = calculation_factory(2)
    on_div = on_fdiv = on_sdiv = on_udiv = calculation_factory(3)
    on_srem = on_urem = calculation_factory(4)
    on_ashr = on_lshr = calculation_factory(5)
    on_and = calculation_factory(6)
    on_shl = calculation_factory(7)
    on_sext = on_zext = on_bitcast = on_sitofp = \
        on_uitofp = on_fpext = on_fptrunc = single_elem_calculation_factory(0)

    del calculation_factory, single_elem_calculation_factory

    def _execute_item(self, statement):
        statement = statement.strip()
        split_index = find_the_correct_space(statement)
        if split_index == -1:
            data_type = None
            data_token = statement
        else:
            data_type = statement[: split_index].strip()
            data_token = statement[split_index:].strip()
        if data_token.find('getelementptr') != -1:
            return self._execute_command(data_token)[0]
        if self.global_env.has_given_key(data_token):
            return self.global_env.get_value(data_token)
        if self.local_env.has_given_key(data_token):
            return self.local_env.get_value(data_token)
        if re.match(r"^\d+$", data_token):
            result_tmp = DataType("i32")
            result_tmp.set_value(num(data_token))
            return result_tmp
        if data_token == 'true' or data_token == 'false':
            result_tmp = DataType("boolean")
            result_tmp.set_value(bool(data_token))
            return result_tmp
        try:
            real_value = num(data_token)
            result_tmp = DataType(data_type)
            result_tmp.set_value(real_value)
            return result_tmp
        except:
            result_tmp = DataType(data_type)
            result_tmp.set_value(data_token)
            return result_tmp


    def _execute_command(self, statement):
        statement = statement.strip()
        split_index = statement.find(' ')
        operator = statement[: split_index].strip()
        arguments = statement[split_index:].strip()
        if not hasattr(self, "on_" + operator):
            return self._execute_item(statement), None, None, None
        return getattr(self, "on_"  + operator)(arguments)


    def _execute_assign(self, statement):
        tmp_arr = statement.split("=")
        target_var = tmp_arr[0].strip()
        if '='.join(tmp_arr[1:]).find("call") != -1:
            self.kernel_codes.set_need_return_token(str(target_var))
        return_value, action, current_index, is_global = self._execute_command('='.join(tmp_arr[1:]))
        self.local_env.add_value(str(target_var), return_value)
        return return_value, action, current_index, is_global


    def run(self, current_stmt):
        if len(re.findall(r"(@|%)\w+\s*=\s*(.*)", current_stmt, re.DOTALL)) != 0:
            return self._execute_assign(current_stmt)
        else:
            return self._execute_command(current_stmt)


if __name__ == '__main__':
    print parse_arguments("double* getelementptr inbounds ([256 x double]* @_ZZL15_trace_sp_sp_fdIfEvPKfPKT_PfiE8row_data, i32 0, i32 0), int* %32")
