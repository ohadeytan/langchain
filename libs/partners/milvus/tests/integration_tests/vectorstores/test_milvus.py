"""Test Milvus functionality."""

from typing import Any, List, Optional

import pytest
from langchain_core.documents import Document

from langchain_milvus.utils.sparse import BM25SparseEmbedding
from langchain_milvus.vectorstores import Milvus
from tests.integration_tests.utils import (
    FakeEmbeddings,
    assert_docs_equal_without_pk,
    fake_texts,
)

#
# To run this test properly, please start a Milvus server with the following command:
#
# ```shell
# wget https://raw.githubusercontent.com/milvus-io/milvus/master/scripts/standalone_embed.sh
# bash standalone_embed.sh start
# ```
#
# Here is the reference:
# https://milvus.io/docs/install_standalone-docker.md
#


def _milvus_from_texts(
    metadatas: Optional[List[dict]] = None,
    ids: Optional[List[str]] = None,
    drop: bool = True,
    **kwargs: Any,
) -> Milvus:
    return Milvus.from_texts(
        fake_texts,
        FakeEmbeddings(),
        metadatas=metadatas,
        ids=ids,
        # connection_args={"uri": "http://127.0.0.1:19530"},
        connection_args={"uri": "./milvus_demo.db"},
        drop_old=drop,
        consistency_level="Strong",
        **kwargs,
    )


def _milvus_multi_vector_from_texts(
    metadatas: Optional[List[dict]] = None,
    drop: bool = True,
    **kwargs: Any,
) -> Milvus:
    return Milvus.from_texts(
        texts=fake_texts,
        embedding=[FakeEmbeddings(), FakeEmbeddings()],
        metadatas=metadatas,
        connection_args={"uri": "./milvus_demo.db"},
        drop_old=drop,
        consistency_level="Strong",
        **kwargs,
    )


def _get_pks(expr: str, docsearch: Milvus) -> List[Any]:
    return docsearch.get_pks(expr)  # type: ignore[return-value]


def test_milvus() -> None:
    """Test end to end construction and search."""
    docsearch = _milvus_from_texts()
    output = docsearch.similarity_search("foo", k=1)
    assert_docs_equal_without_pk(output, [Document(page_content="foo")])


def test_milvus_vector_search() -> None:
    """Test end to end construction and search by vector."""
    docsearch = _milvus_from_texts()
    output = docsearch.similarity_search_by_vector(
        FakeEmbeddings().embed_query("foo"), k=1
    )
    assert_docs_equal_without_pk(output, [Document(page_content="foo")])


def test_milvus_with_metadata() -> None:
    """Test with metadata"""
    docsearch = _milvus_from_texts(metadatas=[{"label": "test"}] * len(fake_texts))
    output = docsearch.similarity_search("foo", k=1)
    assert_docs_equal_without_pk(
        output, [Document(page_content="foo", metadata={"label": "test"})]
    )


def test_milvus_with_id() -> None:
    """Test with ids"""
    ids = ["id_" + str(i) for i in range(len(fake_texts))]
    docsearch = _milvus_from_texts(ids=ids)
    output = docsearch.similarity_search("foo", k=1)
    assert_docs_equal_without_pk(output, [Document(page_content="foo")])

    output = docsearch.delete(ids=ids)
    assert output.delete_count == len(fake_texts)  # type: ignore[attr-defined]

    try:
        ids = ["dup_id" for _ in fake_texts]
        _milvus_from_texts(ids=ids)
    except Exception as e:
        assert isinstance(e, AssertionError)


def test_milvus_with_score() -> None:
    """Test end to end construction and search with scores and IDs."""
    texts = ["foo", "bar", "baz"]
    metadatas = [{"page": i} for i in range(len(texts))]
    docsearch = _milvus_from_texts(metadatas=metadatas)
    output = docsearch.similarity_search_with_score("foo", k=3)
    docs = [o[0] for o in output]
    scores = [o[1] for o in output]
    assert_docs_equal_without_pk(
        docs,
        [
            Document(page_content="foo", metadata={"page": 0}),
            Document(page_content="bar", metadata={"page": 1}),
            Document(page_content="baz", metadata={"page": 2}),
        ],
    )
    assert scores[0] < scores[1] < scores[2]


def test_milvus_max_marginal_relevance_search() -> None:
    """Test end to end construction and MRR search."""
    texts = ["foo", "bar", "baz"]
    metadatas = [{"page": i} for i in range(len(texts))]
    docsearch = _milvus_from_texts(metadatas=metadatas)
    output = docsearch.max_marginal_relevance_search("foo", k=2, fetch_k=3)
    assert_docs_equal_without_pk(
        output,
        [
            Document(page_content="foo", metadata={"page": 0}),
            Document(page_content="bar", metadata={"page": 1}),
        ],
    )


def test_milvus_max_marginal_relevance_search_with_dynamic_field() -> None:
    """Test end to end construction and MRR search with enabling dynamic field."""
    texts = ["foo", "bar", "baz"]
    metadatas = [{"page": i} for i in range(len(texts))]
    docsearch = _milvus_from_texts(metadatas=metadatas, enable_dynamic_field=True)
    output = docsearch.max_marginal_relevance_search("foo", k=2, fetch_k=3)
    assert_docs_equal_without_pk(
        output,
        [
            Document(page_content="foo", metadata={"page": 0}),
            Document(page_content="bar", metadata={"page": 1}),
        ],
    )


def test_milvus_add_extra() -> None:
    """Test end to end construction and MRR search."""
    texts = ["foo", "bar", "baz"]
    metadatas = [{"page": i} for i in range(len(texts))]
    docsearch = _milvus_from_texts(metadatas=metadatas)

    docsearch.add_texts(texts, metadatas)

    output = docsearch.similarity_search("foo", k=10)
    assert len(output) == 6


def test_milvus_no_drop() -> None:
    """Test construction without dropping old data."""
    texts = ["foo", "bar", "baz"]
    metadatas = [{"page": i} for i in range(len(texts))]
    docsearch = _milvus_from_texts(metadatas=metadatas)
    del docsearch

    docsearch = _milvus_from_texts(metadatas=metadatas, drop=False)

    output = docsearch.similarity_search("foo", k=10)
    assert len(output) == 6


def test_milvus_get_pks() -> None:
    """Test end to end construction and get pks with expr"""
    texts = ["foo", "bar", "baz"]
    metadatas = [{"id": i} for i in range(len(texts))]
    docsearch = _milvus_from_texts(metadatas=metadatas)
    expr = "id in [1,2]"
    output = _get_pks(expr, docsearch)
    assert len(output) == 2


def test_milvus_delete_entities() -> None:
    """Test end to end construction and delete entities"""
    texts = ["foo", "bar", "baz"]
    metadatas = [{"id": i} for i in range(len(texts))]
    docsearch = _milvus_from_texts(metadatas=metadatas)
    expr = "id in [1,2]"
    pks = _get_pks(expr, docsearch)
    result = docsearch.delete(pks)
    assert result.delete_count == 2  # type: ignore[attr-defined]


def test_milvus_upsert_entities() -> None:
    """Test end to end construction and upsert entities"""
    texts = ["foo", "bar", "baz"]
    metadatas = [{"id": i} for i in range(len(texts))]
    docsearch = _milvus_from_texts(metadatas=metadatas)
    expr = "id in [1,2]"
    pks = _get_pks(expr, docsearch)
    documents = [
        Document(page_content="test_1", metadata={"id": 1}),
        Document(page_content="test_2", metadata={"id": 3}),
    ]
    ids = docsearch.upsert(pks, documents)
    assert len(ids) == 2  # type: ignore[arg-type]


def test_milvus_enable_dynamic_field() -> None:
    """Test end to end construction and enable dynamic field"""
    texts = ["foo", "bar", "baz"]
    metadatas = [{"id": i} for i in range(len(texts))]
    docsearch = _milvus_from_texts(metadatas=metadatas, enable_dynamic_field=True)
    output = docsearch.similarity_search("foo", k=10)
    assert len(output) == 3

    # When enable dynamic field, any new field data will be added to the collection.
    new_metadatas = [{"id_new": i} for i in range(len(texts))]
    docsearch.add_texts(texts, new_metadatas)

    output = docsearch.similarity_search("foo", k=10)
    assert len(output) == 6

    assert set(docsearch.fields) == {
        docsearch._primary_field,
        docsearch._text_field,
        docsearch._vector_field,
    }


def test_milvus_disable_dynamic_field() -> None:
    """Test end to end construction and disable dynamic field"""
    texts = ["foo", "bar", "baz"]
    metadatas = [{"id": i} for i in range(len(texts))]
    docsearch = _milvus_from_texts(metadatas=metadatas, enable_dynamic_field=False)
    output = docsearch.similarity_search("foo", k=10)
    assert len(output) == 3
    # ["pk", "text", "vector", "id"]
    assert set(docsearch.fields) == {
        docsearch._primary_field,
        docsearch._text_field,
        docsearch._vector_field,
        "id",
    }

    # Try to add new fields "id_new", but since dynamic field is disabled,
    # all fields in the collection is specified as ["pk", "text", "vector", "id"],
    # new field information "id_new" will not be added.
    new_metadatas = [{"id": i, "id_new": i} for i in range(len(texts))]
    docsearch.add_texts(texts, new_metadatas)
    output = docsearch.similarity_search("foo", k=10)
    assert len(output) == 6
    for doc in output:
        assert set(doc.metadata.keys()) == {"id", "pk"}  # `id_new` is not added.

    # When disable dynamic field,
    # missing data of the created fields "id", will raise an exception.
    with pytest.raises(Exception):
        new_metadatas = [{"id_new": i} for i in range(len(texts))]
        docsearch.add_texts(texts, new_metadatas)


def test_milvus_metadata_field() -> None:
    """Test end to end construction and use metadata field"""
    texts = ["foo", "bar", "baz"]
    metadatas = [{"id": i} for i in range(len(texts))]
    docsearch = _milvus_from_texts(metadatas=metadatas, metadata_field="metadata")
    output = docsearch.similarity_search("foo", k=10)
    assert len(output) == 3

    new_metadatas = [{"id_new": i} for i in range(len(texts))]
    docsearch.add_texts(texts, new_metadatas)

    output = docsearch.similarity_search("foo", k=10)
    assert len(output) == 6

    assert set(docsearch.fields) == {
        docsearch._primary_field,
        docsearch._text_field,
        docsearch._vector_field,
        docsearch._metadata_field,
    }


def test_milvus_enable_dynamic_field_with_partition_key() -> None:
    """
    Test end to end construction and enable dynamic field
    with partition_key_field
    """
    texts = ["foo", "bar", "baz"]
    metadatas = [{"id": i, "namespace": f"name_{i}"} for i in range(len(texts))]

    docsearch = _milvus_from_texts(
        metadatas=metadatas, enable_dynamic_field=True, partition_key_field="namespace"
    )

    # filter on a single namespace
    output = docsearch.similarity_search("foo", k=10, expr="namespace == 'name_2'")
    assert len(output) == 1

    # without namespace filter
    output = docsearch.similarity_search("foo", k=10)
    assert len(output) == 3

    assert set(docsearch.fields) == {
        docsearch._primary_field,
        docsearch._text_field,
        docsearch._vector_field,
        docsearch._partition_key_field,
    }


def test_milvus_sparse_embeddings() -> None:
    texts = [
        "In 'The Clockwork Kingdom' by Augusta Wynter, a brilliant inventor discovers "
        "a hidden world of clockwork machines and ancient magic, where a rebellion is "
        "brewing against the tyrannical ruler of the land.",
        "In 'The Phantom Pilgrim' by Rowan Welles, a charismatic smuggler is hired by "
        "a mysterious organization to transport a valuable artifact across a war-torn "
        "continent, but soon finds themselves pursued by assassins and rival factions.",
        "In 'The Dreamwalker's Journey' by Lyra Snow, a young dreamwalker discovers "
        "she has the ability to enter people's dreams, but soon finds herself trapped "
        "in a surreal world of nightmares and illusions, where the boundaries between "
        "reality and fantasy blur.",
    ]
    sparse_embedding_func = BM25SparseEmbedding(corpus=texts)
    docsearch = Milvus.from_texts(
        embedding=sparse_embedding_func,
        texts=texts,
        connection_args={"uri": "./milvus_demo.db"},
        drop_old=True,
    )

    output = docsearch.similarity_search("Pilgrim", k=1)
    assert "Pilgrim" in output[0].page_content


def test_milvus_array_field() -> None:
    """Manually specify metadata schema, including an array_field.
    For more information about array data type and filtering, please refer to
    https://milvus.io/docs/array_data_type.md
    """
    from pymilvus import DataType

    texts = ["foo", "bar", "baz"]
    metadatas = [{"id": i, "array_field": [i, i + 1, i + 2]} for i in range(len(texts))]

    # Manually specify metadata schema, including an array_field.
    # If some fields are not specified, Milvus will automatically infer their schemas.
    docsearch = _milvus_from_texts(
        metadatas=metadatas,
        metadata_schema={
            "array_field": {
                "dtype": DataType.ARRAY,
                "kwargs": {"element_type": DataType.INT64, "max_capacity": 50},
            },
            # "id": {
            #     "dtype": DataType.INT64,
            # }
        },
    )
    output = docsearch.similarity_search("foo", k=10, expr="array_field[0] < 2")
    assert len(output) == 2
    output = docsearch.similarity_search(
        "foo", k=10, expr="ARRAY_CONTAINS(array_field, 3)"
    )
    assert len(output) == 2

    # If we use enable_dynamic_field,
    # there is no need to manually specify metadata schema.
    docsearch = _milvus_from_texts(
        enable_dynamic_field=True,
        metadatas=metadatas,
    )
    output = docsearch.similarity_search("foo", k=10, expr="array_field[0] < 2")
    assert len(output) == 2
    output = docsearch.similarity_search(
        "foo", k=10, expr="ARRAY_CONTAINS(array_field, 3)"
    )
    assert len(output) == 2


def test_milvus_multi_vector_embeddings() -> None:
    sparse_embedding_func = BM25SparseEmbedding(corpus=fake_texts)
    dense_embedding_func_1 = FakeEmbeddings()
    dense_embeddings_func_2 = FakeEmbeddings()
    docsearch = Milvus.from_texts(
        embedding=[
            sparse_embedding_func,
            dense_embedding_func_1,
            dense_embeddings_func_2,
        ],
        texts=fake_texts,
        connection_args={"uri": "./milvus_demo.db"},
        drop_old=True,
    )
    output = docsearch.similarity_search(query=fake_texts[0], k=1)
    assert_docs_equal_without_pk(output, [Document(page_content=fake_texts[0])])


def test_milvus_multi_vector_with_index_params() -> None:
    """Test setting index params which are different from the defaults."""
    index_param_1 = {
        "metric_type": "COSINE",
        "index_type": "HNSW",
    }
    index_param_2 = {
        "metric_type": "IP",
        "index_type": "HNSW",
    }

    docsearch = Milvus.from_texts(
        texts=fake_texts,
        embedding=[FakeEmbeddings(), FakeEmbeddings()],
        index_params=[index_param_1, index_param_2],
        vector_field=["vec_field_1", "vec_field_2"],
        connection_args={"uri": "./milvus_demo.db"},
        drop_old=True,
    )

    index_1 = docsearch.col.indexes[0]
    assert index_1.field_name == "vec_field_1"
    assert index_1.params["metric_type"] == "COSINE"
    assert docsearch.search_params[0]["metric_type"] == "COSINE"

    index_2 = docsearch.col.indexes[1]
    assert index_2.field_name == "vec_field_2"
    assert index_2.params["metric_type"] == "IP"
    assert docsearch.search_params[1]["metric_type"] == "IP"


def test_milvus_multi_vector_search_with_ranker() -> None:
    """Test hybrid search with specified ranker"""
    from langchain_core.embeddings import Embeddings

    class FixedValuesEmbeddings(Embeddings):
        def __init__(self, *, documents_base_val: float = 1.0, query_val: float = 1.0):
            self.documents_val = documents_base_val
            self.query_val = query_val

        def embed_documents(self, texts: List[str]) -> List[List[float]]:
            return [[self.documents_val + i] * 10 for i in range(len(texts))]

        def embed_query(self, text: str) -> List[float]:
            return [float(self.query_val)] * 10

    # Force the query vector to always be identical to the first document
    embedding_1 = FixedValuesEmbeddings(documents_base_val=0.0, query_val=float(0))
    # Force the query to always be identical to the last document
    embedding_2 = FixedValuesEmbeddings(
        documents_base_val=0.0, query_val=float(len(fake_texts))
    )
    docsearch = Milvus.from_texts(
        embedding=[embedding_1, embedding_2],
        texts=fake_texts,
        connection_args={"uri": "./milvus_demo.db"},
        drop_old=True,
    )

    query = fake_texts[0]
    output = docsearch.similarity_search(
        query=query,
        ranker_type="weighted",
        ranker_params={"weights": [1.0, 0.0]},
        k=1,
    )
    assert_docs_equal_without_pk(output, [Document(page_content=fake_texts[0])])

    output = docsearch.similarity_search(
        query=query,
        ranker_type="weighted",
        ranker_params={"weights": [0.0, 1.0]},
        k=1,
    )
    assert_docs_equal_without_pk(output, [Document(page_content=fake_texts[-1])])


def test_milvus_multi_vector_with_single_embeddings_raises_exception() -> None:
    with pytest.raises(ValueError) as exception:
        _ = Milvus.from_texts(
            embedding=[FakeEmbeddings()],
            texts=fake_texts,
            connection_args={"uri": "./milvus_demo.db"},
            drop_old=True,
        )
    assert exception.type is ValueError


# if __name__ == "__main__":
#     test_milvus()
#     test_milvus_vector_search()
#     test_milvus_with_metadata()
#     test_milvus_with_id()
#     test_milvus_with_score()
#     test_milvus_max_marginal_relevance_search()
#     test_milvus_max_marginal_relevance_search_with_dynamic_field()
#     test_milvus_add_extra()
#     test_milvus_no_drop()
#     test_milvus_get_pks()
#     test_milvus_delete_entities()
#     test_milvus_upsert_entities()
#     test_milvus_enable_dynamic_field()
#     test_milvus_disable_dynamic_field()
#     test_milvus_metadata_field()
#     test_milvus_enable_dynamic_field_with_partition_key()
#     test_milvus_sparse_embeddings()
#     test_milvus_array_field()
#     test_milvus_multi_vector_embeddings()
#     test_milvus_multi_vector_with_index_params()
#     test_milvus_multi_vector_search_with_ranker()
