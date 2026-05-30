# Dorabot-Orchestrator
# Dorabot Orchestrator – Architecture Diagrams

This document keeps the diagrams and structure so you can always return to them.

---

## 1️⃣ Project Structure – Hierarchy Diagram

```
orchestrator
├── main.py
├── config.py
├── schemas.py
├── event_bus.py
│
├── services/
│   ├── specs.py
│   └── manager.py
│
├── http/
│   ├── app.py
│   └── routers/
│       ├── events.py
│       ├── actions.py
│       └── admin.py
│
├── domain/
│   ├── state.py
│   ├── safety.py
│   ├── navigation.py
│   ├── perception.py
│   ├── media.py
│   └── user.py
│
└── adapters/
    ├── ai_agent_client.py
    ├── ros2_adapter.py
    ├── emergency_contact_client.py
    └── music_player_client.py
```

---

## 2️⃣ Logical Responsibility Diagram

```
          ┌──────────────────────────────────────────┐
          │                main.py                   │
          │        starts app + services             │
          └──────────────────────────────────────────┘
                               │
                               ▼
          ┌──────────────────────────────────────────┐
          │                 http/                    │
          │   FastAPI app + routers (Events/Actions) │
          └──────────────────────────────────────────┘
                               │
                               ▼
          ┌──────────────────────────────────────────┐
          │                domain/                   │
          │ Business logic + Robot brain             │
          │  • safety       • perception             │
          │  • navigation   • media                  │
          │  • user         • global state           │
          └──────────────────────────────────────────┘
                               │
                               ▼
          ┌──────────────────────────────────────────┐
          │                adapters/                 │
          │ Bridges to external world:               │
          │  • ROS2 (motion/nav)                     │
          │  • AI agent                              │
          │  • Emergency Contact                     │
          │  • Music Player                          │
          └──────────────────────────────────────────┘
                               │
                               ▼
          ┌──────────────────────────────────────────┐
          │                services/                 │
          │ Launch + monitor external processes      │
          │ (slam, perception, ai agent, etc.)       │
          └──────────────────────────────────────────┘
```

---

## 3️⃣ Runtime Interaction – Fall Detection Example

```
 Perception/Fall Detection  ───────►  /events/fall_detected
                                      (http/routers/events.py)
                                               │
                                               ▼
                                       domain/safety.py
                                               │
                                               ▼
                              adapters/ai_agent_client.py
                                 (asks user "Did you fall?")
                                               │
                                               ▼
                              AI Agent ───────► user speaks
                                               │
                                               ▼
                     AI Agent ───────►  /actions/fall_dialog_result
                                               │
                                               ▼
                                      domain/safety.py
                                               │
                             yes ──────────────┴───────────── no
                                               │
                                               ▼
                     adapters/emergency_contact_client.py
```

---

## 4️⃣ Component Block Diagram

```
┌──────────────┐         ┌─────────────────────┐
│  Sensors     │  POST   │        HTTP         │
│  (Fall/SLAM) ├────────►│  /events , /actions │
└──────────────┘         └─────────┬───────────┘
                                    │
                                    ▼
                          ┌──────────────────┐
                          │      DOMAIN      │
                          │ safety/nav/media │
                          └───────┬──────────┘
                                  │
            ┌─────────────────────┼──────────────────────┐
            ▼                     ▼                      ▼
   ┌─────────────┐       ┌───────────────┐      ┌─────────────────┐
   │    ROS2     │       │  AI Agent     │      │ Emergency Call   │
   │ movement    │       │ interaction   │      │ (Twilio/etc)     │
   └─────────────┘       └───────────────┘      └─────────────────┘
```

---

You can keep adding future diagrams and updates here. Let me know when we evolve the architecture and we’ll update this doc together.

