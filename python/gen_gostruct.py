import argparse
import json
import sys
from re import sub


class GoStructType:

    def __init__(self, name):
        self.name = name
        self.attr_types = {}
        self.go_code = ''

    def appendCode(self, code):
        self.go_code = self.go_code + code

    def hasAttr(self, attr):
        return attr in self.attr_types

    def getAttrType(self, attr):
        return self.attr_types[attr]

    def length(self):
        return len(self.attr_types.keys())


def empty_struct():
    empty = GoStructType("EmptyStruct")
    empty.appendCode('type EmptyStruct struct {}\n')
    return empty


def is_list(attrType):
    return attrType.startswith('[]')


def camel_case(s):
    ls = sub(r"(_|-)+", " ", s).split()
    ls = [w[0].upper() + w[1:] for w in ls]
    return ''.join(ls)


def type_of_value(v):
    if v is None:
        return 'any'
    elif isinstance(v, int):
        return 'int64'
    elif isinstance(v, float):
        return 'float64'
    elif isinstance(v, bool):
        return 'bool'
    elif isinstance(v, str):
        return 'string'
    elif isinstance(v, dict):
        return "Dict"
    elif isinstance(v, list):
        return "List"
    else:
        raise ValueError("Unexpected value: " + str(v))


def find_same_struct(attr_types, go_structs):
    for struct in go_structs:
        if len(attr_types.keys()) != struct.length():
            continue

        isSame = True
        for attr_name, attr_type in attr_types.items():
            if not struct.hasAttr(attr_name):
                isSame = False
                break

            t = struct.getAttrType(attr_name)
            if t == attr_type:
                continue
            if t == 'any' or attr_type == 'any':
                continue
            if is_list(t) and is_list(attr_type):
                if t == '[]any' or attr_type == '[]any':
                    continue

            isSame = False

        if isSame:
            return struct

    return None


class Generator:

    def __init__(self, root, go_pkg):
        self.all_structs = []
        self.counter = 0
        self.root = root
        self.go_code = f'package {go_pkg}\n'
        self.done = False

    def generate(self):
        if self.done:
            return

        _ = self.gen_obj(self.root)
        for st in self.all_structs:
            self.go_code += st.go_code

        self.done = True

    def gen_obj(self, o):
        r = GoStructType('')
        attr_types = {}
        if len(o.keys()) > 0:
            for attr_name, attr_val in o.items():
                attr_type = type_of_value(attr_val)
                if attr_type == 'Dict':
                    st = self.gen_obj(attr_val)
                    attr_type = st.name
                elif attr_type == 'List':
                    attr_type = self.gen_list(attr_val)
                attr_types[attr_name] = attr_type

        st = find_same_struct(attr_types, self.all_structs)
        if st is not None:
            return st

        r.name = 'GenStruct_' + str(self.counter)
        self.counter += 1
        r.attr_types = attr_types
        r.appendCode(f'\ntype {r.name} struct {{\n')
        for attr_name, attr_type in attr_types.items():
            r.appendCode(f'\t{camel_case(attr_name)} {attr_type} \
            `json:"{attr_name},omitempty"`\n')
        r.appendCode('}\n')
        self.all_structs.insert(0, r)
        return r

    def gen_list(self, ls):
        if len(ls) == 0:
            return '[]any'
        val = ls[0]
        val_type = type_of_value(val)
        if val_type == 'Dict':
            st = self.gen_obj(val)
            val_type = st.name
        elif val_type == 'List':
            val_type = self.gen_list(val)
        return f'[]{val_type}'


def parse_argument():
    parser = argparse.ArgumentParser(
        description='Generate Go Structs from a json object.')
    parser.add_argument(
        'json_str',
        metavar='json_str',
        nargs='?',
        help='the input json object, either this or the file path \
        (option: -ipath) that contains a json object must be provided')
    parser.add_argument(
        '-ipath',
        '--input_file_path',
        dest='ipath',
        metavar='path',
        nargs='?',
        type=argparse.FileType('r'),
        help='path of the input file that contains a json object')
    parser.add_argument('-gopkg',
                        '--go_package',
                        dest='gopkg',
                        default='main',
                        nargs='?',
                        help='package name of the generated code')

    args = parser.parse_args()
    if args.json_str is None and args.ipath is None:
        sys.exit('Error: no json input!')
    if args.json_str is not None:
        objstr = args.json_str
    else:
        objstr = args.ipath.read()

    try:
        root = json.loads(objstr)
    except json.decoder.JSONDecodeError as e:
        sys.exit('Error: invalid json input: ' + str(e))
    if not isinstance(root, dict):
        sys.exit("Error: Json input must be an object!")
    return root, args.gopkg


if __name__ == '__main__':
    root, gopkg = parse_argument()
    gen = Generator(root, gopkg)
    gen.generate()
    print(gen.go_code)
