from pydantic import BaseModel
from typing import List
from pydantic import BaseModel, Field
from typing import List

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2"
RUNS_PER_PROMPT = 3
MAX_RETRIES = 3
RESULTS_DIR = "results"
TEMPERATURES = [0.0,  0.7] #0.2, 0.5, 1.0,

class UniversalResponse(BaseModel):
    """A universal schema enforcing Chain-of-Thought reasoning for all prompts."""
    reasoning: str = Field(description="Step-by-step logical deduction or thought process.")
    final_answer: str = Field(description="The exact answer, code, or summary requested.")
    confidence_score: float = Field(description="A score between 0.0 and 1.0 indicating confidence.")

PROMPTS = {
        # Category 1: Factual Recall & Technical Definitions
        "01": "Explain the difference between a REST API and a GraphQL API in exactly 3 sentences.",
        # "02": "Explain the ACID principles in database management. Keep it brief.",
        # "03": "Explain the concept of container orchestration in simple terms.",
        # "04": "What is the difference between a compiled language and an interpreted language?",
        # "05": "How does a Content Delivery Network (CDN) reduce latency?",

        # # Category 2: Strict Instruction Following & Format Constraints
        # "06": "Summarize the difference between TCP and UDP. You must respond in exactly two bullet points.",
        # "07": "Provide a strictly technical explanation of how a load balancer distributes traffic. Do not use any real-world analogies.",
        # "08": "Write a 50-word paragraph about artificial intelligence. The paragraph must contain the word 'future' exactly three times.",
        # "09": "List three popular Linux distributions. Your entire response must be in all uppercase letters.",
        # "10": "Write a single sentence explaining what DNS is. Do not use the letter 'e' anywhere in your response.",

        # # Category 3: Coding & Syntax Generation
        # "11": "Write a Python function that takes a list of integers and returns only the even numbers. Include type hints.",
        # "12": "Write a basic Dockerfile to containerize a compiled Java Spring Boot 4 application.",
        # "13": "Write a React functional component that renders a button and a counter, incrementing the counter when clicked. Include TypeScript interfaces.",
        # "14": "Write a bash script that searches for all '.log' files in the current directory and archives them into a single 'tar.gz' file.",
        # "15": "Create a regular expression that validates standard email addresses, and explain how it works in one sentence.",

        # # Category 4: Logic & Multi-step Reasoning
        # "16": "If a Kubernetes cluster has 5 nodes and each node can handle 100 requests per second, how long will it take to process 30,000 requests in total? Explain your math.",
        # "17": "A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. How much does the ball cost?",
        # "18": "Arrange the following CI/CD pipeline steps in the correct logical execution order: Deploy to Production, Run Unit Tests, Build Docker Image, Push to Registry, Code Commit.",
        # "19": "Sally has 3 brothers. Each brother has 2 sisters. How many sisters does Sally have?",
        # "20": "You have a 3-gallon jug and a 5-gallon jug, and an unlimited supply of water. Explain step-by-step how to measure exactly 4 gallons of water.",

        # # Category 5: Context Processing & Extraction
        # "21": "Extract the core problem and solution from this text: 'The predictive scaling system failed because the baseline model could not handle seasonality. The team resolved this by implementing a hybrid SARIMAX and Bi-LSTM architecture to forecast resource spikes.'",
        # "22": "Summarize the plot of the movie 'The Matrix' in a single, comma-separated sentence.",
        # "23": "Identify all the proper nouns in the following sentence: 'On Tuesday, Sarah drove her Toyota to the Microsoft office in Seattle.'",
        # "24": "Read this review: 'The battery life is amazing but the screen is too dim for outdoor use.' Classify the sentiment as Positive, Negative, or Mixed, and provide a one-sentence justification.",
        # "25": "Extract only the dates and times from this meeting request: 'Let's push the deployment from Wednesday at 2 PM to Thursday morning around 9:30 AM.'",

        # # Category 6: Data Transformation & Formatting
        # "26": "Generate a JSON object representing a server configuration with the fields: hostname, ip_address, port, and is_active. Do not output any markdown or explanation text.",
        # "27": "Write a simple SQL query to select all user emails from a 'users' table where the account status is 'suspended', ordered by signup date descending.",
        # "28": "Convert the following list into a markdown table with headers Name, Role, and Department: Alice - Engineer - IT, Bob - Manager - HR, Charlie - Designer - Product.",
        # "29": "Write a YAML configuration for a GitHub Actions workflow that triggers on push to the main branch and runs 'npm test'.",
        # "30": "Convert this JSON object into XML: {\"employee\": {\"name\": \"John\", \"age\": 30, \"city\": \"New York\"}}",

        # # Category 7: Math & Computation
        # "31": "What is the derivative of 3x^2 + 2x - 5? Show your work step-by-step.",
        # "32": "Calculate the compound interest on $5,000 invested at 4% annual interest rate for 5 years, compounded annually.",
        # "33": "A server has 64GB of RAM. If the OS uses 4GB, and each Docker container requires 1.5GB, what is the maximum number of full containers that can run?",
        # "34": "Convert the hexadecimal number 1A to binary and decimal.",
        # "35": "If the probability of a system failure is 0.05 per day, what is the probability that the system runs flawlessly for 7 consecutive days?",

        # # Category 8: Professional Writing & Tone Adaptation
        # "36": "Write a professional, two-paragraph email to a development team announcing that a new automated backend deployment pipeline is now active in the staging environment.",
        # "37": "Explain the concept of caching using strictly technical concepts. Avoid all real-world analogies.",
        # "38": "Act as a grumpy senior systems administrator. Write a 3-sentence response to a junior developer asking why they shouldn't just test their code in production.",
        # "39": "Write a formal project proposal executive summary for migrating a monolithic application to a microservices architecture.",
        # "40": "Write a brief incident report summary for a database outage that lasted 45 minutes due to an expired TLS certificate."
    }
