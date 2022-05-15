
import msg
import msg_ros 
import subprocess

# from roswire.exceptions import ParsingError

def get_datatype(input, msg_found = []):
    firstData : msg_ros.ROSMsgFormat = get_datatype_input(input)
    msg_found.append(input)
    output = []
    baseTypes = ["float64","uint32","time","string","float64[36]"]
    fieldsMsg = firstData.fields
    for field in fieldsMsg:
        fieldtyp : str = field.typ
        fieldtypSplit = fieldtyp.split("/")
        fieldtyp = fieldtypSplit[-1]
        if not fieldtyp in msg_found and not fieldtyp in baseTypes:
            print("get_datatype",fieldtyp)
            output += get_datatype(fieldtyp,msg_found)
    output.append(firstData)
    return output


def get_datatype_input(input):
    message = (f"rosmsg show -r {input}")
    print(message)
    data = subprocess.check_output(message, shell=True).decode("utf-8")
    dataSplit = data.split('\n')
    messageInfo = dataSplit[0][1:-2]
    package, name = messageInfo.split('/')
    print("package = ", package)
    print("name = ",name)
    result = ""
    for line in dataSplit[1:]:
        if not line == "" and not line[0] == '#':
            result += line + '\n'

    print(result) 
    msg =  msg_ros.ROSMsgFormat.from_string(package, name, result)

    print(msg)
    return msg



result = get_datatype("Twist")
for res in result:
    print('\n')
    print(res)

