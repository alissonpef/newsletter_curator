from unittest.mock import Mock

from hermes.use_cases.search_knowledge import SearchKnowledgeUseCase


def test_execute_empty_query():
    vector_store_mock = Mock()
    use_case = SearchKnowledgeUseCase(vector_store_mock)

    result = use_case.execute(query="  ")
    assert result["total"] == 0
    assert result["query"] == ""
    assert result["results"] == []
    vector_store_mock.search.assert_not_called()


def test_execute_valid_query():
    vector_store_mock = Mock()
    vector_store_mock.search.return_value = [
        {"id": "1", "date_ref": "2023-10-01", "content": "Test result"}
    ]
    use_case = SearchKnowledgeUseCase(vector_store_mock)

    result = use_case.execute(query="stocks", n_results=5)
    
    assert result["total"] == 1
    assert result["query"] == "stocks"
    assert result["results"][0]["date_label"] == "domingo, 1 de outubro"
    vector_store_mock.search.assert_called_once_with(
        "stocks", n_results=5, date_from=None, date_to=None
    )


def test_get_topic_timeline_empty():
    vector_store_mock = Mock()
    use_case = SearchKnowledgeUseCase(vector_store_mock)

    result = use_case.get_topic_timeline(topic="")
    assert result["total_occurrences"] == 0
    assert result["by_date"] == []
    vector_store_mock.get_topic_frequency.assert_not_called()


def test_get_topic_timeline_valid():
    vector_store_mock = Mock()
    vector_store_mock.get_topic_frequency.return_value = [
        {"date_ref": "2023-10-02", "count": 3},
        {"date_ref": "2023-10-03", "count": 2},
    ]
    use_case = SearchKnowledgeUseCase(vector_store_mock)

    result = use_case.get_topic_timeline(topic="economy", days=10)
    
    assert result["total_occurrences"] == 5
    assert result["days"] == 10
    assert result["by_date"][0]["date_label"] == "segunda, 2 de outubro"
    vector_store_mock.get_topic_frequency.assert_called_once_with("economy", days=10)


def test_get_vector_stats():
    vector_store_mock = Mock()
    vector_store_mock.get_stats.return_value = {"collections": 1, "documents": 100}
    use_case = SearchKnowledgeUseCase(vector_store_mock)

    result = use_case.get_vector_stats()
    assert result["collections"] == 1
    assert result["documents"] == 100
    vector_store_mock.get_stats.assert_called_once()
