# Suggested Devpost entry (edit after real testing)

## Project name
SmartPay AI — Explainable Agentic Checkout

## Elevator pitch
An AI shopping copilot that recommends products within your budget, explains why, and only prepares a PayPal Sandbox checkout after explicit human approval.

## Inspiration
Agentic commerce is exciting, but allowing an AI to initiate payments without transparent limits creates a trust problem. We wanted a simple rule: the AI can advise and prepare a transaction; the buyer retains the final decision.

## What it does
The customer describes a desired product and sets a maximum purchase price and monthly funds available. SmartPay AI uses a local machine-learning retrieval model to find relevant examples in a fictional catalogue, enforces budget constraints, and gives an explanation that can optionally be enhanced by an LLM. After the customer chooses an option, a server-side integration with PayPal's Orders v2 creates the order. The PayPal Checkout SDK collects buyer approval and the server captures a Sandbox payment.

## How we built it
Python / FastAPI / scikit-learn TF-IDF / optional OpenAI-compatible LLM / HTML, CSS, JS / PayPal REST API Orders v2 / PayPal JavaScript SDK. No real money or production PayPal credentials are used.

## Challenges
Balancing agent autonomy with buyer control; making server-side spending limits authoritative; isolating model output from payment execution; creating a clear end-to-end demo in a short timeframe.

## Accomplishments we're proud of
[Update this after testing:] Transparent matching, dual budget checks, explicit approval and server-authoritative order amounts. PayPal Sandbox payment confirmed with a test buyer account: [Yes / Not yet].

## What's next
Multi-merchant comparisons with live merchant integrations, user-defined risk preferences, transaction audit logs, and fully authenticated multi-user session storage.

## Open-source code
[YOUR PUBLIC REPOSITORY URL]

## Demo video
[YOUR PUBLIC YOUTUBE URL]

## Setup
See README.md. A hosted deployment is optional under the official rules if judges can run the repository.

## Transparency
The catalogue is entirely fictitious. The recommendation model is local ML; optional natural-language explanations are provided by an LLM only when configured. The prototype is not an actual price-comparison engine or financial advisor. All payment calls target the PayPal Sandbox environment.
