import pytest

# TODO: The method of a nonlocal counter is not great
#       There should be a way to setup a fixture or a mock
#       to check how many times the underlying function is called


def test_no_params(patched_decorator):
    counter = 0

    def no_params_func():
        nonlocal counter
        counter += 1
        return counter

    cached_func = patched_decorator()(no_params_func)

    assert cached_func() == 1
    assert cached_func() == 1
    assert counter == 1


def test_method(patched_decorator):
    counter = 0

    class A:
        def f(self):
            nonlocal counter
            counter += 1
            return 1

    a = A()

    cached_func = patched_decorator()(a.f)

    assert cached_func() == 1
    assert cached_func() == 1
    assert counter == 1


def test_one_arg(patched_decorator):
    counter = 0

    def one_arg_func(a):
        nonlocal counter
        counter += 1
        return a + a

    cached_func = patched_decorator()(one_arg_func)

    assert cached_func(1) == 2
    assert counter == 1
    assert cached_func(1) == 2
    assert cached_func(a=1) == 2
    assert counter == 1

    assert cached_func(2) == 4
    assert counter == 2
    assert cached_func(2) == 4
    assert cached_func(a=2) == 4
    assert counter == 2

    assert cached_func("1") == "11"
    assert counter == 3
    assert cached_func("1") == "11"
    assert cached_func(a="1") == "11"
    assert counter == 3


def test_multiple_args(patched_decorator):
    counter = 0

    def multiple_args_func(a, b):
        nonlocal counter
        counter += 1
        return a + b

    cached_func = patched_decorator()(multiple_args_func)

    assert cached_func(1, 1) == 2
    assert counter == 1
    assert cached_func(1, 1) == 2
    assert cached_func(1, b=1) == 2
    assert cached_func(a=1, b=1) == 2
    assert counter == 1

    assert cached_func(1, 2) == 3
    assert counter == 2
    assert cached_func(1, 2) == 3
    assert cached_func(1, b=2) == 3
    assert cached_func(a=1, b=2) == 3
    assert counter == 2


def test_keyword_only_args(patched_decorator):
    counter = 0

    def keyword_only_args_func(a, *, b):
        nonlocal counter
        counter += 1
        return a + b

    cached_func = patched_decorator()(keyword_only_args_func)

    #
    # Test that the cached function raises the same exception
    # as the non-cached function
    #
    try:
        keyword_only_args_func(1, 1)
    except Exception as e:
        expected_exception = e.__class__

    with pytest.raises(expected_exception):
        cached_func(1, 1)

    assert cached_func(1, b=1) == 2
    assert counter == 1
    assert cached_func(1, b=1) == 2
    assert cached_func(a=1, b=1) == 2
    assert counter == 1

    assert cached_func(1, b=2) == 3
    assert counter == 2
    assert cached_func(1, b=2) == 3
    assert cached_func(a=1, b=2) == 3
    assert counter == 2


def test_var_args(patched_decorator):
    counter = 0

    def var_args_func(*args, **kwargs):
        nonlocal counter
        counter += 1
        return sum(args) + sum(kwargs.values())

    cached_func = patched_decorator()(var_args_func)

    assert cached_func(1, b=1) == 2
    assert counter == 1
    assert cached_func(1, b=1) == 2
    assert counter == 1

    assert cached_func(1, b=2) == 3
    assert counter == 2
    assert cached_func(1, b=2) == 3
    assert counter == 2

    # for these types of function scrat can't know if
    # f(1, 2) is the same as f(1, b=2) so it's run again
    assert cached_func(1, 2) == 3
    assert counter == 3
    assert cached_func(1, 2) == 3
    assert counter == 3

    assert cached_func(a=1, b=2) == 3
    assert counter == 4
    assert cached_func(a=1, b=2) == 3
    assert counter == 4


def test_code_changes(patched_decorator):
    counter = 0

    def code_changes_func():
        nonlocal counter
        counter += 1
        return 1

    cached_func = patched_decorator()(code_changes_func)

    assert cached_func() == 1
    assert cached_func() == 1
    assert counter == 1

    # a new function with the same name and code should re-use the nut
    def code_changes_func():
        nonlocal counter
        counter += 1
        return 1

    cached_func = patched_decorator()(code_changes_func)

    assert cached_func() == 1
    assert cached_func() == 1
    assert counter == 1

    # a new function with the same name but different code should create a new nut
    def code_changes_func():
        nonlocal counter
        counter += 1
        return 2  # <- difference

    cached_func = patched_decorator()(code_changes_func)

    assert cached_func() == 2
    assert cached_func() == 2
    assert counter == 2


def test_multiple_func(patched_decorator):
    counter_1 = 0

    def multi_func_1():
        nonlocal counter_1
        counter_1 += 1
        return 1

    cached_func_1 = patched_decorator()(multi_func_1)

    counter_2 = 0

    def multi_func_2():
        nonlocal counter_2
        counter_2 += 1
        return 1

    cached_func_2 = patched_decorator()(multi_func_2)

    assert cached_func_1() == 1
    assert cached_func_2() == 1
    assert counter_1 == 1
    assert counter_2 == 1

    assert cached_func_1() == 1
    assert cached_func_2() == 1
    assert counter_1 == 1
    assert counter_2 == 1
