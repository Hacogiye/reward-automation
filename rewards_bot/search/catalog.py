"""Danh mục truy vấn tìm kiếm: câu dài, có nghĩa, mẫu câu chỉ áp cho chủ đề hợp với nó.

Mỗi lĩnh vực gồm nhiều nhóm, mỗi nhóm là một trong ba dạng:
  {"topics": [...], "templates": ["... {t} ..."]}        chủ đề x mẫu câu
  {"pairs": [(a, b), ...], "templates": ["{a} vs {b} ..."]}  so sánh hai thứ
  {"queries": [...]}                                      câu viết sẵn
"""

import json
from functools import lru_cache
from pathlib import Path

# ============================================================================ IT
_IT_TOOL_TEMPLATES = [
    "how to install and configure {t} on ubuntu server",
    "{t} configuration example for production",
    "{t} performance tuning tips for high traffic",
    "common {t} errors and how to fix them",
    "{t} tutorial for beginners step by step",
    "{t} best practices for security and reliability",
    "how to monitor {t} with prometheus and grafana",
    "{t} interview questions for devops engineers",
]
_IT_CONCEPT_TEMPLATES = [
    "what is {t} and why is it important",
    "{t} explained with a real world example",
    "how does {t} work under the hood",
    "{t} explained simply for beginners",
    "common {t} mistakes in system design",
    "{t} interview questions for backend developers",
    "when should you use {t} in a web application",
    "{t} pros and cons in large scale systems",
]

IT_NETWORK = {
    "Server & Mạng": [
        {"topics": ["nginx", "apache http server", "haproxy", "traefik", "caddy server", "bind9 dns",
                    "wireguard vpn", "openvpn", "pfsense firewall", "squid proxy"],
         "templates": _IT_TOOL_TEMPLATES},
        {"topics": ["load balancing", "reverse proxy", "dns resolution", "tcp three way handshake",
                    "subnetting", "vlan", "bgp routing", "nat traversal", "http/2 multiplexing", "http/3 quic",
                    "content delivery network", "anycast routing", "tls termination", "sticky sessions",
                    "ipv6 addressing", "network latency"],
         "templates": ["what is {t} and why is it important", "{t} explained with a real world example",
                       "how does {t} work step by step", "{t} explained simply for beginners",
                       "how to troubleshoot {t} problems on linux", "{t} interview questions for network engineers"]},
        {"pairs": [("nginx", "apache"), ("tcp", "udp"), ("haproxy", "nginx"), ("layer 4", "layer 7 load balancing"),
                   ("round robin", "least connections load balancing"), ("ipv4", "ipv6"), ("wireguard", "openvpn"),
                   ("forward proxy", "reverse proxy"), ("http/2", "http/3")],
         "templates": ["{a} vs {b} which one should i use", "difference between {a} and {b} explained",
                       "{a} vs {b} performance comparison"]},
        {"queries": [
            "how to set up nginx as a reverse proxy with ssl using lets encrypt",
            "how to configure nginx load balancing between multiple backend servers",
            "nginx 502 bad gateway error causes and fixes",
            "how to calculate subnet mask and number of hosts per subnet",
            "what happens when you type a url into the browser step by step",
            "how to set up a home lab network with vlans and a managed switch",
            "how to enable gzip and brotli compression in nginx",
            "how to configure rate limiting in nginx to stop brute force attacks",
        ]},
    ],
}

IT_DEVOPS = {
    "DevOps & Cloud": [
        {"topics": ["docker", "kubernetes", "terraform", "ansible", "jenkins", "github actions", "gitlab ci",
                    "helm charts", "argo cd", "prometheus", "grafana", "elk stack", "redis", "rabbitmq",
                    "apache kafka", "postgresql", "mongodb", "elasticsearch"],
         "templates": _IT_TOOL_TEMPLATES},
        {"topics": ["ci/cd pipeline", "infrastructure as code", "blue green deployment", "canary release",
                    "container orchestration", "service mesh", "auto scaling", "observability",
                    "serverless computing", "database replication", "database sharding", "caching strategy",
                    "message queue", "event driven architecture", "microservices architecture",
                    "rate limiting", "circuit breaker pattern", "cap theorem", "eventual consistency",
                    "horizontal scaling"],
         "templates": _IT_CONCEPT_TEMPLATES},
        {"pairs": [("docker", "virtual machine"), ("kubernetes", "docker swarm"), ("kafka", "rabbitmq"),
                   ("sql", "nosql databases"), ("monolith", "microservices"), ("aws", "azure"),
                   ("terraform", "ansible"), ("redis", "memcached"), ("postgresql", "mysql"),
                   ("vertical scaling", "horizontal scaling")],
         "templates": ["{a} vs {b} which one should i use", "difference between {a} and {b} explained",
                       "{a} vs {b} for a small startup"]},
        {"queries": [
            "how to deploy a node js app to kubernetes with zero downtime",
            "how to write a dockerfile for a python flask application",
            "kubernetes pod stuck in crashloopbackoff how to debug",
            "how to reduce docker image size with multi stage builds",
            "aws free tier services you can use without paying",
            "how to set up a ci cd pipeline with github actions and docker",
            "how does redis persistence work rdb vs aof",
            "how to design a url shortener system design interview",
            "how to back up a postgresql database automatically every day",
        ]},
    ],
}

IT_IOT = {
    "IoT & Phần cứng": [
        {"topics": ["esp32", "arduino uno", "raspberry pi 5", "zigbee", "mqtt broker", "lorawan",
                    "home assistant", "node red", "esphome", "stm32 microcontroller"],
         "templates": ["{t} project ideas for beginners", "how to get started with {t} step by step",
                       "{t} tutorial with sensors and wifi", "common {t} problems and how to fix them",
                       "best {t} projects for smart home automation", "{t} power consumption and battery life tips"]},
        {"topics": ["edge computing", "industrial iot", "digital twin", "embedded linux",
                    "real time operating system", "iot security", "sensor fusion", "pulse width modulation",
                    "i2c communication", "spi protocol", "uart serial communication", "fpga"],
         "templates": ["what is {t} and how is it used", "{t} explained with a real world example",
                       "how does {t} work in embedded systems", "{t} explained simply for beginners"]},
        {"pairs": [("mqtt", "http for iot"), ("zigbee", "z-wave"), ("esp32", "raspberry pi"),
                   ("arduino", "esp32"), ("i2c", "spi"), ("lora", "nb-iot")],
         "templates": ["{a} vs {b} which one should i use", "difference between {a} and {b} explained"]},
        {"queries": [
            "how to build a temperature and humidity monitor with esp32 and mqtt",
            "how to connect esp32 to home assistant over wifi",
            "how to flash esphome firmware to a smart plug",
            "how to read sensor data from arduino and send it to the cloud",
            "best ssd and cpu for a budget gaming pc build",
            "how to undervolt a gpu to reduce temperature",
            "ddr5 vs ddr4 ram is the upgrade worth it for gaming",
            "how to choose a power supply wattage for a new pc build",
        ]},
    ],
}

IT_SECURITY = {
    "Bảo mật": [
        {"topics": ["sql injection", "cross site scripting", "csrf attack", "man in the middle attack",
                    "ransomware", "phishing", "ddos attack", "privilege escalation", "zero day exploit",
                    "brute force attack", "session hijacking", "dns spoofing"],
         "templates": ["what is {t} and how does it work", "how to prevent {t} in web applications",
                       "real world examples of {t}", "{t} explained for beginners with examples",
                       "how to detect {t} on a company network"]},
        {"topics": ["oauth 2.0", "json web token", "tls handshake", "public key infrastructure",
                    "zero trust security", "two factor authentication", "password hashing with bcrypt",
                    "single sign on", "web application firewall", "penetration testing", "siem",
                    "end to end encryption"],
         "templates": ["what is {t} and why is it important", "how does {t} work step by step",
                       "{t} explained with a real world example", "what developers should know about {t}"]},
        {"pairs": [("symmetric", "asymmetric encryption"), ("authentication", "authorization"),
                   ("oauth", "saml"), ("jwt", "session cookies"), ("ids", "ips")],
         "templates": ["difference between {a} and {b} explained", "{a} vs {b} which one is more secure"]},
        {"queries": [
            "how to secure a linux server after a fresh install",
            "owasp top 10 vulnerabilities explained with examples",
            "how to set up fail2ban to protect ssh from brute force",
            "how to tell if an email is a phishing attempt",
            "how to use nmap to scan your own network",
            "how to store passwords securely in a database",
            "what to do if your account was hacked step by step",
        ]},
    ],
}

IT_DEV = {
    "Lập trình": [
        {"topics": ["python decorators", "python asyncio", "rust ownership and borrowing", "javascript promises",
                    "javascript event loop", "typescript generics", "react hooks", "react server components",
                    "go goroutines and channels", "kotlin coroutines", "java streams api", "c++ smart pointers",
                    "git rebase", "regular expressions", "sql window functions", "sql indexes", "graphql",
                    "websockets", "unit testing with pytest", "dependency injection", "solid principles",
                    "design patterns", "big o notation", "recursion"],
         "templates": ["{t} tutorial with practical examples", "{t} explained for beginners with code examples",
                       "{t} best practices for clean and maintainable code",
                       "{t} common mistakes and how to avoid them", "how to use {t} in a real project",
                       "{t} interview questions and answers", "advanced {t} tips for experienced developers"]},
        {"topics": ["binary search", "dynamic programming", "graph traversal bfs and dfs", "dijkstra algorithm",
                    "hash table", "linked list", "binary search tree", "heap data structure", "trie",
                    "sliding window technique", "two pointers technique", "union find", "topological sort",
                    "backtracking"],
         "templates": ["{t} explained with step by step examples", "{t} leetcode problems to practice",
                       "how to implement {t} in python", "{t} time and space complexity",
                       "when to use {t} in coding interviews"]},
        {"pairs": [("python", "javascript"), ("react", "vue"), ("rest", "graphql"), ("java", "kotlin"),
                   ("rust", "go"), ("git merge", "git rebase"), ("process", "thread"), ("stack", "heap memory"),
                   ("compiled", "interpreted languages"), ("next js", "remix")],
         "templates": ["{a} vs {b} which one should i learn", "difference between {a} and {b} explained",
                       "{a} vs {b} performance comparison"]},
        {"queries": [
            "how to build a rest api with fastapi and postgresql",
            "how to structure a large react project folder",
            "how to undo the last git commit without losing changes",
            "how to write clean code tips from senior developers",
            "how to prepare for a software engineer interview in 3 months",
            "best way to learn programming from zero in 2026",
            "how to read and understand a large codebase quickly",
            "how to debug memory leaks in a node js application",
        ]},
    ],
}

IT_AI = {
    "Dữ liệu & AI": [
        {"topics": ["transformer architecture", "attention mechanism", "retrieval augmented generation",
                    "vector database", "fine tuning large language models", "gradient descent",
                    "backpropagation", "convolutional neural network", "reinforcement learning",
                    "overfitting and regularization", "random forest", "k means clustering",
                    "principal component analysis", "embedding models", "prompt engineering",
                    "diffusion models"],
         "templates": ["what is {t} and how does it work", "{t} explained with a simple example",
                       "{t} explained intuitively without math", "how to implement {t} in python",
                       "{t} use cases in real world applications"]},
        {"pairs": [("machine learning", "deep learning"), ("supervised", "unsupervised learning"),
                   ("pytorch", "tensorflow"), ("data warehouse", "data lake"), ("rag", "fine tuning"),
                   ("pandas", "polars")],
         "templates": ["{a} vs {b} explained with practical examples", "difference between {a} and {b} for beginners"]},
        {"queries": [
            "how to build a chatbot that answers questions from your own documents",
            "how to clean messy data with pandas step by step",
            "how to choose evaluation metrics for a classification model",
            "how much math do you need for machine learning",
            "how to run a large language model locally on your own pc",
            "roadmap to become a data scientist from scratch",
        ]},
    ],
}

# ============================================================================ Game
_GAMES = ["roblox", "minecraft", "league of legends", "fortnite", "valorant", "counter strike 2", "dota 2",
          "genshin impact", "honkai star rail", "elden ring", "apex legends", "pubg mobile", "mobile legends",
          "teamfight tactics", "overwatch 2", "the legend of zelda tears of the kingdom", "stardew valley",
          "pokemon scarlet and violet", "call of duty warzone", "arena of valor"]

GAMES = {
    "Game": [
        {"topics": _GAMES,
         "templates": ["{t} tips and tricks for beginners", "{t} best settings for high fps on a low end pc",
                       "{t} latest update patch notes explained", "how to get better at {t} fast",
                       "{t} tier list for the current season", "is {t} still worth playing in 2026",
                       "{t} mistakes every new player makes", "{t} esports tournament schedule and results"]},
        {"pairs": [("valorant", "counter strike 2"), ("league of legends", "dota 2"), ("fortnite", "apex legends"),
                   ("roblox", "minecraft"), ("genshin impact", "honkai star rail"), ("ps5", "xbox series x"),
                   ("steam deck", "rog ally"), ("mobile legends", "arena of valor")],
         "templates": ["{a} vs {b} which game is better for beginners", "{a} vs {b} comparison for casual players"]},
        {"queries": [
            # Roblox
            "how to make your first game in roblox studio step by step",
            "roblox lua scripting tutorial for beginners",
            "best roblox horror games to play with friends",
            "how to earn robux legally without spending money",
            "best roblox tycoon and simulator games right now",
            "how to fix roblox lag and low fps on pc",
            "how to make a roblox obby with checkpoints",
            "roblox blox fruits best fruit for grinding levels",
            # League of Legends / TFT
            "league of legends best jungle champions to climb solo queue",
            "how to last hit better in league of legends",
            "league of legends wave management guide for beginners",
            "how to ward properly as a support in league of legends",
            "best champions for new league of legends players",
            "league of legends worlds championship results and highlights",
            "teamfight tactics best comps for the current set",
            "how does matchmaking and mmr work in league of legends ranked",
            # Fortnite
            "how to build and edit faster in fortnite",
            "fortnite new season map changes and new weapons",
            "best fortnite creative maps to practice aim",
            "fortnite zero build tips to get more wins",
            "how to get free v bucks legit in fortnite",
            "fortnite best keybinds for pc players",
            # Minecraft
            "minecraft best redstone farms for survival",
            "how to build an automatic iron farm in minecraft",
            "best minecraft mods and modpacks this year",
            "how to set up a minecraft server for friends",
            "minecraft enchantment guide for best armor and tools",
            # FPS
            "valorant best crosshair settings used by pro players",
            "how to improve aim in valorant with aim trainers",
            "valorant agent tier list for solo queue",
            "counter strike 2 smoke lineups for mirage",
            "how to counter strafe properly in counter strike 2",
            "apex legends best legends for solo ranked",
            "best mouse sensitivity and dpi for fps games",
            # MOBA / gacha / other
            "dota 2 best heroes for beginners to learn",
            "genshin impact best team comps for spiral abyss",
            "honkai star rail best characters to pull for",
            "mobile legends best heroes for solo rank this season",
            "elden ring best beginner build and weapon",
            "stardew valley money making guide for the first year",
            "best free to play games on steam right now",
            "best co op games to play with friends online",
            "upcoming video game releases this month",
            "how to start streaming games on twitch with obs",
            "best gaming monitor 144hz vs 240hz is it worth it",
            "how to become a professional esports player",
        ]},
    ],
}

# ============================================================================ Học thuật
MATH = {
    "Toán": [
        {"topics": ["eigenvalues and eigenvectors", "fourier transform", "bayes theorem", "taylor series",
                    "markov chains", "linear regression", "matrix multiplication", "complex numbers",
                    "integration by parts", "differential equations", "probability distributions",
                    "central limit theorem", "hypothesis testing and p value", "graph theory",
                    "modular arithmetic", "set theory", "limits and continuity", "vector calculus",
                    "laplace transform", "combinatorics"],
         "templates": ["{t} explained intuitively with visual examples", "{t} explained step by step with worked examples", "real world applications of {t}",
                       "how to understand {t} for university students", "{t} practice problems with solutions",
                       "why is {t} important in computer science"]},
        {"queries": [
            "how to prove a statement by mathematical induction",
            "how to calculate standard deviation by hand",
            "why does dividing by zero not work",
            "how to study for a calculus exam effectively",
            "how is linear algebra used in machine learning",
            "what is the difference between correlation and causation",
        ]},
    ],
}

SCIENCE = {
    "Vật lý & Vũ trụ": [
        {"topics": ["quantum entanglement", "special relativity", "general relativity", "schrodinger equation",
                    "maxwell's equations", "entropy and the second law of thermodynamics", "superconductivity",
                    "nuclear fusion", "dark matter", "dark energy", "black holes", "neutron stars",
                    "gravitational waves", "the double slit experiment", "semiconductors", "the standard model",
                    "the big bang theory", "exoplanets"],
         "templates": ["{t} explained simply without complicated math", "the science behind {t} explained",
                       "latest scientific research and discoveries about {t}",
                       "why is {t} important in modern physics", "{t} explained for high school students",
                       "common misconceptions people have about {t}"]},
        {"queries": [
            "how do nuclear fusion reactors like iter work",
            "why is the sky blue explained with physics",
            "how do solar panels convert sunlight into electricity",
            "how does gps use relativity to stay accurate",
            "what would happen if you fell into a black hole",
            "james webb space telescope latest discoveries",
            "how do rockets work in the vacuum of space",
        ]},
    ],
    "Hóa & Sinh học": [
        {"topics": ["crispr gene editing", "dna replication", "protein folding", "the krebs cycle",
                    "photosynthesis", "mitochondria", "the immune system", "mrna vaccines", "stem cells",
                    "neurotransmitters", "gut microbiome", "natural selection", "chemical bonding",
                    "redox reactions", "acids and bases", "catalysts", "polymers", "lithium ion batteries"],
         "templates": ["the science behind {t} explained step by step", "{t} explained simply with everyday examples",
                       "latest scientific research and discoveries about {t}",
                       "{t} explained step by step with diagrams", "why is {t} important for life and health"]},
        {"queries": [
            "how do antibiotics work and why does resistance happen",
            "how do vaccines train the immune system",
            "why do we need sleep according to neuroscience",
            "how does caffeine affect the brain",
            "how are lithium ion batteries made and recycled",
        ]},
    ],
}

ECON = {
    "Kinh tế & Tài chính": [
        {"topics": ["compound interest", "index funds", "inflation", "interest rates", "credit scores",
                    "an emergency fund", "dividend investing", "bond yields", "the stock market",
                    "mortgage rates", "personal budgeting", "retirement savings", "supply and demand",
                    "opportunity cost", "gdp", "quantitative easing", "exchange rates", "recession"],
         "templates": ["how does {t} work explained simply", "{t} explained for beginners in simple words",
                       "how {t} affects everyday life", "common mistakes people make with {t}",
                       "{t} explained with real examples"]},
        {"queries": [
            "how to make a monthly budget when you are a student",
            "how to start investing with a small amount of money",
            "why do central banks raise interest rates to fight inflation",
            "how does the 50 30 20 budgeting rule work",
            "what is the difference between stocks and bonds",
            "how to build good credit history from scratch",
            "how do startups raise money from venture capital",
        ]},
    ],
}

# ============================================================================ Đời sống
LIFE = {
    "Sức khỏe": [
        {"topics": ["sleep quality", "back pain", "posture", "gut health", "stress", "eye strain",
                    "blood pressure", "cholesterol levels", "energy levels", "focus and concentration"],
         "templates": ["how to improve {t} naturally", "daily habits that improve {t}",
                       "foods that help with {t}", "simple exercises to improve {t}"]},
        {"topics": ["intermittent fasting", "creatine", "vitamin d", "omega 3", "magnesium", "protein powder",
                    "cold showers", "meditation", "zone 2 cardio", "strength training"],
         "templates": ["benefits and side effects of {t}", "what does science say about {t}",
                       "{t} for beginners how to start safely", "{t} pros and cons according to research"]},
        {"queries": [
            "how much water should you drink per day",
            "how to fix posture after sitting at a desk all day",
            "full body workout plan for beginners at home",
            "how to fall asleep faster when you have insomnia",
            "how many steps a day do you need to stay healthy",
            "how to reduce screen time and avoid eye strain",
            "symptoms of burnout and how to recover",
        ]},
    ],
    "Ẩm thực": [
        {"topics": ["pho bo", "bun cha", "banh mi", "banh xeo", "ramen", "pad thai", "sourdough bread",
                    "tiramisu", "kimchi", "green curry", "beef stew", "cheesecake", "dim sum", "lasagna",
                    "paella", "mochi", "fried rice", "croissants"],
         "templates": ["how to make authentic {t} at home", "easy {t} recipe for beginners",
                       "history and origin of {t}", "secret tips to make better {t}"]},
        {"queries": [
            "healthy meal prep ideas for a busy week",
            "how to cook rice perfectly without a rice cooker",
            "best high protein breakfast ideas",
            "how to sharpen a kitchen knife properly",
            "how long can cooked food stay in the fridge",
            "easy dinner recipes with chicken and vegetables",
        ]},
    ],
    "Du lịch": [
        {"topics": ["Ha Long Bay", "Da Lat", "Hoi An", "Sapa", "Phu Quoc", "Ninh Binh", "Hue", "Kyoto",
                    "Seoul", "Bangkok", "Singapore", "Bali", "Taipei", "Paris", "Iceland", "Istanbul",
                    "Lisbon", "the Swiss Alps", "New Zealand", "Machu Picchu"],
         "templates": ["things to do in {t} for first time visitors", "best time of year to visit {t}",
                       "3 day itinerary for {t} on a budget", "local food you must try in {t}",
                       "hidden gems in {t} that tourists miss", "how to get around {t} cheaply"]},
        {"queries": [
            "how to find cheap flights and best time to book",
            "what to pack for a one week backpacking trip",
            "how to apply for a japan tourist visa",
            "travel insurance is it worth it for short trips",
            "best travel apps for planning a trip abroad",
        ]},
    ],
    "Lịch sử": [
        {"topics": ["the Roman Empire", "the Ly dynasty", "the Ming dynasty", "ancient Egypt", "the Tran dynasty",
                    "the Byzantine Empire", "the Mongol Empire", "the Khmer Empire", "the Ottoman Empire",
                    "the Maya civilization", "the Inca Empire", "the Champa kingdom"],
         "templates": ["history of {t} explained", "why did {t} rise and fall", "most important rulers of {t}",
                       "what daily life was like in {t}", "best documentaries about {t}"]},
        {"topics": ["the Battle of Dien Bien Phu", "the Industrial Revolution", "the Renaissance", "the Silk Road",
                    "the Cold War", "the French Revolution", "the Meiji Restoration", "the Battle of Bach Dang",
                    "the Apollo program", "the fall of the Berlin Wall", "the printing press", "World War I"],
         "templates": ["{t} explained in simple terms", "timeline of {t} key events", "causes and effects of {t}",
                       "how {t} changed the world", "best documentaries about {t}"]},
    ],
    "Thể thao": [
        {"topics": ["the premier league", "the champions league", "the nba", "formula 1", "the v league",
                    "the tour de france", "the badminton world championships"],
         "templates": ["{t} latest results and highlights this week", "{t} standings and schedule this season",
                       "greatest players in {t} history", "how does {t} format work explained"]},
        {"topics": ["badminton", "table tennis", "tennis", "volleyball", "marathon running", "swimming",
                    "rock climbing", "pickleball", "cycling", "boxing", "chess"],
         "templates": ["{t} rules explained for beginners", "how to get started with {t} as an adult",
                       "training tips to get better at {t}", "common {t} mistakes beginners make",
                       "best equipment for {t} beginners on a budget"]},
        {"queries": [
            "how to train for your first 10k run",
            "best chess openings for beginners to learn",
            "how does the offside rule work in football",
            "formula 1 race calendar this season",
            "how to choose the right badminton racket",
        ]},
    ],
    "Giải trí": [
        {"topics": ["studio ghibli", "marvel movies", "korean dramas", "anime", "true crime documentaries",
                    "fantasy novels", "sci fi movies", "stand up comedy", "podcasts", "manga", "broadway musicals",
                    "lofi music", "jazz music", "classic movies"],
         "templates": ["best {t} of all time ranked", "underrated {t} you should watch",
                       "where to start with {t} if you are new", "new {t} releases this month"]},
        {"queries": [
            "best movies to watch on netflix this week",
            "how to start learning guitar as an adult",
            "best books to read if you liked harry potter",
            "how to start a podcast with a small budget",
            "best anime series for people who never watched anime",
        ]},
    ],
    "Học tập & Ngoại ngữ": [
        {"topics": ["ielts writing task 2", "ielts speaking", "toeic listening", "japanese kanji", "korean grammar",
                    "chinese characters", "english pronunciation", "essay writing", "public speaking",
                    "critical thinking", "note taking", "speed reading"],
         "templates": ["how to improve {t} quickly", "{t} tips from teachers", "free resources to practice {t}",
                       "{t} study plan for 30 days", "common mistakes in {t}"]},
        {"queries": [
            "how to use spaced repetition with anki to remember more",
            "pomodoro technique does it really work for studying",
            "how to stay focused while studying at home",
            "how to apply for scholarships to study abroad",
            "best online courses for learning new skills for free",
            "how to write a good cv with no work experience",
        ]},
    ],
    "Nhà cửa & DIY": [
        {"topics": ["a small apartment", "a home office", "a balcony garden", "a minimalist bedroom",
                    "a small kitchen", "a home gym"],
         "templates": ["ideas to decorate {t} on a budget", "how to organize {t} to save space",
                       "{t} setup ideas and tips"]},
        {"queries": [
            "how to fix a leaky faucet step by step",
            "best indoor plants that are hard to kill",
            "how to set up a smart home on a budget",
            "how to remove mold from bathroom walls",
            "how to choose a good air purifier for a bedroom",
            "how to paint a room without leaving streaks",
            "how to start composting kitchen waste at home",
        ]},
    ],
    "Ô tô & Xe": [
        {"topics": ["electric cars", "hybrid cars", "motorbikes", "e-bikes", "used cars", "car batteries", "tires"],
         "templates": ["how to maintain {t} to make them last longer", "{t} buying guide what to check",
                       "common problems with {t} and how to fix them"]},
        {"queries": [
            "how often should you change engine oil",
            "how to check tire pressure and why it matters",
            "electric car charging at home cost and setup",
            "how to pass the driving test on the first try",
            "vinfast electric car review and range test",
            "how to maintain a scooter in rainy season",
        ]},
    ],
    "Thiên nhiên & Địa lý": [
        {"topics": ["Mount Everest", "the Mekong River", "the Sahara Desert", "the Mariana Trench", "Antarctica",
                    "the Amazon rainforest", "the Great Barrier Reef", "Son Doong cave", "the Himalayas",
                    "the Galapagos Islands", "Lake Baikal", "Victoria Falls"],
         "templates": ["interesting facts about {t} most people do not know", "how was {t} formed over millions of years", "how climate change affects {t}",
                       "wildlife that lives in {t}"]},
        {"topics": ["octopuses", "elephants", "honey bees", "dolphins", "owls", "penguins", "tardigrades",
                    "fireflies", "sea turtles", "wolves"],
         "templates": ["how smart are {t} really", "where do {t} live and what do they eat",
                       "surprising facts about {t} that sound made up", "why are {t} important for the ecosystem"]},
    ],
}

CATEGORIES: dict = {}
for _part in (IT_NETWORK, IT_DEVOPS, IT_IOT, IT_SECURITY, IT_DEV, IT_AI, GAMES, MATH, SCIENCE, ECON, LIFE):
    CATEGORIES.update(_part)


def _expand(group: dict) -> list:
    if "queries" in group:
        return list(group["queries"])
    if "pairs" in group:
        return [tpl.format(a=a, b=b) for a, b in group["pairs"] for tpl in group["templates"]]
    return [tpl.format(t=t) for t in group["topics"] for tpl in group["templates"]]


# Từ khóa phổ biến (tên phim, người nổi tiếng, xu hướng tìm kiếm...): câu ngắn, đã lọc từ 18+.
# Là một lĩnh vực riêng nên QueryBank xen kẽ nó với các lĩnh vực ở trên như mọi lĩnh vực khác.
POPULAR_CATEGORY = "Từ khóa phổ biến"
POPULAR_FILE = Path(__file__).with_name("popular_queries.json")


@lru_cache(maxsize=1)
def popular_queries() -> tuple:
    """Danh sách từ khóa phổ biến; thiếu file hoặc file hỏng thì trả về rỗng."""
    try:
        data = json.loads(POPULAR_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    return tuple(q.strip() for q in data if isinstance(q, str) and q.strip())


def all_queries(popular: bool = True) -> list:
    """[(lĩnh vực, câu search)], không trùng (không phân biệt hoa thường)."""
    out, seen = [], set()
    for cat, groups in CATEGORIES.items():
        for g in groups:
            for q in _expand(g):
                if q.lower() not in seen:
                    seen.add(q.lower())
                    out.append((cat, q))
    if popular:
        for q in popular_queries():
            if q.lower() not in seen:
                seen.add(q.lower())
                out.append((POPULAR_CATEGORY, q))
    return out


# Câu cho search ảnh (Bing Images): thứ có hình để xem, không dùng bộ câu kiến thức ở trên
IMAGE_QUERIES = [
    "aurora borealis iceland", "ha long bay aerial view", "hoi an lantern festival night", "rice terraces mu cang chai",
    "son doong cave photos", "fansipan sunrise", "kyoto cherry blossom", "swiss alps winter village",
    "santorini sunset", "milky way night sky", "great barrier reef coral", "sahara desert dunes",
    "cute red panda", "snow leopard in the wild", "hummingbird close up", "sea turtle underwater",
    "golden retriever puppy", "shiba inu", "british shorthair cat", "octopus camouflage",
    "studio ghibli scenery wallpaper", "cyberpunk city wallpaper 4k", "minimalist desk setup",
    "mechanical keyboard custom", "gaming pc rgb build", "home office setup ideas", "scandinavian living room",
    "japanese garden design", "small balcony garden", "bonsai tree", "modern tiny house",
    "pho bo vietnamese", "banh mi sandwich", "sushi platter", "ramen bowl", "matcha latte art",
    "latte art heart", "sourdough bread crumb", "tiramisu dessert", "fruit tart",
    "minecraft castle build", "minecraft medieval village", "roblox avatar ideas", "fortnite skins",
    "league of legends splash art", "valorant agents wallpaper", "genshin impact landscape", "elden ring concept art",
    "pokemon cards collection", "zelda tears of the kingdom scenery", "james webb telescope images",
    "saturn rings close up", "nebula hubble photo", "volcano eruption lava", "lightning storm photography",
    "vintage film camera", "porsche 911 classic", "vinfast vf8", "cafe racer motorcycle", "electric scooter design",
    "watercolor landscape painting", "ink drawing city sketch", "pixel art landscape", "origami crane",
]
