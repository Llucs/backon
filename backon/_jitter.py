import random


def random_jitter(value: float) -> float:
    return value + random.random()


def full_jitter(value: float) -> float:
    return random.uniform(0, value)
