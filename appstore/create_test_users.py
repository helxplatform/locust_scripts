import sys
import string
import random

users_list = []
characters = string.ascii_letters + string.digits


def random_password():
    password = ''.join(random.choice(characters) for _ in range(10))
    return password


def create_users(num_of_users):
    for i in range(0, num_of_users):
        user_name = "HelxUser" + str(i+1)
        password = random_password()
        email = user_name + "@email.com"
        user_creds = (user_name, password, email)
        users_list.append(user_creds)
    return users_list


create_users(int(sys.argv[1]))

with open("users.txt", 'w') as users:
    for user in users_list:
        username, password, email = user
        users.write(f"{username},{password},{email}\n")


