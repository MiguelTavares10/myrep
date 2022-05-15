# import roswire
# from roswire.common import Time, MsgFormat
# from roswire.ros2 import ROS2MsgFormat
import subprocess

# from roswire.exceptions import ParsingError

input = "Twist"
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
#msg =  ROS2MsgFormat.from_string("geometry_msg", "Twist", data)
