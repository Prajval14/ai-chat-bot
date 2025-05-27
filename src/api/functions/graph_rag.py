import os
from dotenv import load_dotenv

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain.prompts import PromptTemplate

from langchain_community.vectorstores import Neo4jVector
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.graphs import Neo4jGraph
from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_experimental.graph_transformers import LLMGraphTransformer

def main():
    load_dotenv()

    openai_api_key = os.getenv("OPENAI_API_KEY")
    neo4j_url = os.getenv("NEO4J_URL")
    neo4j_username = os.getenv("NEO4J_USERNAME")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
    llm = ChatOpenAI(model_name="gpt-4o-mini", openai_api_key=openai_api_key)

    graph = Neo4jGraph(
        url=neo4j_url,
        username=neo4j_username,
        password=neo4j_password
    )

    TXT_PATH = "../docs/nestle_sample_data.txt"
    with open(TXT_PATH, "r", encoding="utf-8") as f:
        text = f.read()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=40)
    docs = text_splitter.create_documents([text])

    lc_docs = []
    for i, doc in enumerate(docs):
        lc_docs.append(Document(
            page_content=doc.page_content.replace("\n", " "),
            metadata={'source': TXT_PATH, 'chunk': i}
        ))

    graph.query("MATCH (n) DETACH DELETE n;")

    transformer = LLMGraphTransformer(
        llm=llm,
        node_properties=True,
        relationship_properties=True
    )

    graph_documents = transformer.convert_to_graph_documents(lc_docs)
    graph.add_graph_documents(graph_documents, include_source=True)

    index = Neo4jVector.from_existing_graph(
        embedding=embeddings,
        url=neo4j_url,
        username=neo4j_username,
        password=neo4j_password,
        database="neo4j",
        node_label="Entity",
        text_node_properties=["id", "text"],
        embedding_node_property="embedding",
        index_name="vector_index",
        keyword_index_name="entity_index",
        search_type="hybrid"
    )

    schema = graph.get_schema

    template = """
    Task: Generate a Cypher statement to query the graph database.

    Instructions:
    Use only relationship types and properties provided in schema.
    Do not use other relationship types or properties that are not provided.

    schema:
    {schema}

    Note: Do not include explanations or apologies in your answers.
    Do not answer questions that ask anything other than creating Cypher statements.
    Do not include any text other than generated Cypher statements.

    Question: {question}
    """

    question_prompt = PromptTemplate(
        template=template,
        input_variables=["schema", "question"]
    )

    qa = GraphCypherQAChain.from_llm(
        llm=llm,
        graph=graph,
        cypher_prompt=question_prompt,
        verbose=True,
        allow_dangerous_requests=True
    )

if __name__ == "__main__":
    main()