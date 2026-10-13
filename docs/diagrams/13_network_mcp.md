# Network MCP door

How a call from an AI tool on another machine is let in, run, and written down.

```mermaid
flowchart TD
    CALLER["AI tool on another machine<br/>(a colleague's assistant, a company LLM front end)"]
    PROXY["Gateway or proxy<br/>TLS, company sign-in<br/>(not part of ReqBot)"]
    ASK["POST /mcp<br/>Authorization: Bearer code"]

    subgraph DOOR["reqbot mcp --http"]
        A{"Code in the codes file<br/>or REQBOT_MCP_CODES?<br/>read on every request"}
        REF1["Refused, 401<br/>a wrong guess waits one second<br/>the attempt is logged"]
        H{"Host name on the allow-list?<br/>(when --allow-host is given)"}
        REF2["Refused, 421"]
        W{"A free slot within 30 seconds?<br/>(at most 4 at once by default)"}
        BUSY["Told the server is busy<br/>logged"]
        T["One of seven read-only tools<br/>in a worker thread<br/>no synthesis"]
        S{"Did it fail?"}
        E["A short sentence and a reference<br/>no address, folder or model name"]
        OK["The answer<br/>quotes with citations and sources"]
        LOG[("Request log<br/>time, code name, tool,<br/>shortened arguments, result, duration,<br/>the real error text on a failure")]
    end

    BACK[("Qdrant, the model machine,<br/>the processed files<br/>read only")]

    CALLER --> PROXY
    PROXY --> ASK
    ASK --> A
    A -->|no| REF1
    A -->|"yes: the code's name goes with the call"| H
    H -->|no| REF2
    H -->|yes| W
    W -->|no| BUSY
    W -->|yes| T
    T --> BACK
    BACK --> T
    T --> S
    S -->|yes| E
    S -->|no| OK
    E --> LOG
    OK --> LOG
    BUSY --> LOG
    REF1 --> LOG

    classDef built fill:#d1fae5,stroke:#059669,color:#064e3b;
    classDef drop fill:#fee2e2,stroke:#dc2626,color:#7f1d1d;
    classDef data fill:#fef3c7,stroke:#d97706,color:#78350f;
    classDef side fill:#e0e7ff,stroke:#4f46e5,color:#1e1b4b;
    class T,OK built;
    class REF1,REF2,BUSY,E drop;
    class BACK,LOG data;
    class PROXY side;
```

Only the seven read-only tools exist behind this door. A code opens nothing else: it is not the admin code, and no tool adds, changes or removes a document.

Back to the [diagram index](README.md).
