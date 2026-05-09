from agent import Agent

def test():
    a = Agent()
    print("Running agent...")
    gen = a.run(user_input="test")
    for event in gen:
        print(f"Event: {event}")

if __name__ == "__main__":
    test()
