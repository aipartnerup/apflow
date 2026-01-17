import pytest
from src.apflow.core.utils.helpers import extract_first_json_object, extract_all_json_object, extract_last_json_object

# Test extract_first_json_object

def test_extract_first_json_object_array():
    # Should extract the first non-empty JSON array
    output = 'Some text before [1, 2, 3] some text after {"a": 1}'
    result = extract_first_json_object(output)
    assert result == [1, 2, 3]

def test_extract_first_json_object_object():
    # Should extract the first non-empty JSON object if no array exists
    output = 'Random output {"foo": "bar"} trailing text'
    result = extract_first_json_object(output)
    assert result == {"foo": "bar"}

def test_extract_first_json_object_empty():
    # Should raise ValueError if no valid JSON found
    output = 'No JSON here!'
    with pytest.raises(ValueError):
        extract_first_json_object(output)

def test_extract_first_json_object_skip_empty():
    # Should skip empty arrays/objects
    output = '[] {} [4]'
    result = extract_first_json_object(output)
    assert result == [4]

# Test extract_all_json_object

def test_extract_all_json_object_array_and_object():
    # Should prioritize arrays over objects (default mixed)
    output = '{"a": 1} [10, 20] {"b": 2}'
    all_json = extract_all_json_object(output)
    assert all(isinstance(j, list) for j in all_json)
    assert all_json == [[10, 20]]

def test_extract_all_json_object_scope_list():
    # Should return only arrays
    output = '[1,2] {"a":1} [3,4] {"b":2}'
    all_json = extract_all_json_object(output, scope="list")
    assert all_json == [[1,2], [3,4]]

def test_extract_all_json_object_scope_object():
    # Should return only objects
    output = '[1,2] {"a":1} [3,4] {"b":2}'
    all_json = extract_all_json_object(output, scope="object")
    assert all_json == [{"a":1}, {"b":2}]

def test_extract_all_json_object_scope_all():
    # Should return all arrays and objects in order
    output = 'foo [1] bar {"a":1} [2,3] {"b":2} baz'
    all_json = extract_all_json_object(output, scope="all")
    assert all_json == [[1], {"a":1}, [2,3], {"b":2}]

def test_extract_all_json_object_scope_all_edge_cases():
    # Should skip empty arrays/objects and preserve order
    output = '[] {} [4] {"x":1} [5,6] {}'
    all_json = extract_all_json_object(output, scope="all")
    assert all_json == [[4], {"x":1}, [5,6]]

def test_extract_all_json_object_only_object():
    # Should return all objects if no arrays exist (default mixed)
    output = 'foo {"x": 1} bar {"y": 2, "z": 3}'
    all_json = extract_all_json_object(output)
    assert all(isinstance(j, dict) for j in all_json)
    assert all_json == [{"x": 1}, {"y": 2, "z": 3}]

def test_extract_all_json_object_none():
    # Should raise ValueError if no valid JSON found
    output = 'no json!'
    with pytest.raises(ValueError):
        extract_all_json_object(output)

# Test extract_last_json_object

def test_extract_last_json_object_array():
    # Should return the last non-empty array
    output = '[1] [2, 3] {"a": 1}'
    result = extract_last_json_object(output)
    assert result == [2, 3]

def test_extract_last_json_object_object():
    # Should return the last non-empty object if no arrays
    output = '{"a": 1} {"b": 2, "c": 3}'
    result = extract_last_json_object(output)
    assert result == {"b": 2, "c": 3}

def test_extract_last_json_object_skip_empty():
    # Should skip empty arrays/objects and return the last valid one
    output = '[] {} [4, 5] {"x": 1}'
    result = extract_last_json_object(output)
    assert result == [4, 5]

def test_extract_last_json_object_none():
    # Should raise ValueError if no valid JSON found
    output = 'no valid json here'
    with pytest.raises(ValueError):
        extract_last_json_object(output)

    def test_extract_first_json_object_scope_all():
        output = '[1] {"a":1} [2,3] {"b":2}'
        result = extract_first_json_object(output, scope="all")
        assert result == [1]

    def test_extract_last_json_object_scope_all():
        output = '[1] {"a":1} [2,3] {"b":2}'
        result = extract_last_json_object(output, scope="all")
        assert result == {"b":2}

    def test_extract_first_json_object_scope_object():
        output = '[1] {"a":1} [2,3] {"b":2}'
        result = extract_first_json_object(output, scope="object")
        assert result == {"a":1}

    def test_extract_last_json_object_scope_list():
        output = '[1] {"a":1} [2,3] {"b":2}'
        result = extract_last_json_object(output, scope="list")
        assert result == [2,3]
