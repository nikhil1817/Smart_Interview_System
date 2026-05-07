# InterviewPreppy Frontend

## Project Structure

```
frontend/
├── public/
│   └── index.html
├── src/
│   ├── assets/           # Images, icons, etc.
│   ├── components/       # Reusable components
│   ├── context/          # React context for state management
│   ├── hooks/            # Custom React hooks
│   ├── pages/            # Page components
│   ├── services/         # API and utility services
│   ├── styles/           # CSS files
│   ├── utils/            # Helper functions and constants
│   ├── App.jsx
│   ├── index.jsx
│   └── index.css
├── .env                  # Environment variables
├── package.json
└── README.md
```

## Getting Started

### Install dependencies
```bash
npm install
```

### Start development server
```bash
npm start
```

### Build for production
```bash
npm build
```

## Available Components

- `QuestionDisplay` - Display interview questions
- `AgentPanel` - Show current agent information
- `AnswerInput` - Text/voice input for answers
- `EvaluationCard` - Display evaluation scores
- `Header` - Top navigation
- `ModeSelector` - Interview mode selection
- `Statistics` - Display stats and metrics

## Available Pages

- `Home` - Landing page
- `InterviewUI` - Main interview page
- `Report` - Interview results
- `Dashboard` - User dashboard

## Services

- `apiService` - Backend API calls
- `audioService` - Audio recording/playback
- `storageService` - Local storage management

## Custom Hooks

- `useInterview` - Interview state management
- `useAudio` - Audio operations

## Context

- `InterviewContext` - Global interview state
