"""
Module: test_example.py
Description: Provides basic tests for the 'add' function to demonstrate the testing setup.
"""

import pytest


def add(a: int, b: int) -> int:
    """
    Add two integers.

    Parameters:
        a (int): The first integer.
        b (int): The second integer.

    Returns:
        int: The sum of a and b.
    """
    return a + b


def test_add_positive_numbers():
    """
    Test the add function with positive numbers.
    """
    result = add(2, 3)
    assert result == 5, f"Expected 5, got {result}"


def test_add_negative_numbers():
    """
    Test the add function with negative numbers.
    """
    result = add(-2, -3)
    assert result == -5, f"Expected -5, got {result}"


def test_add_mixed_sign_numbers():
    """
    Test the add function with one negative and one positive number.
    """
    result = add(-2, 3)
    assert result == 1, f"Expected 1, got {result}"


if __name__ == "__main__":
    # Run the tests when the module is executed directly.
    pytest.main([__file__])
