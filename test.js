import http from "k6/http";

export const options = {
  scenarios: {
    chatbot: {
      executor: "per-vu-iterations",
      vus: 10,
      iterations: 1,
      maxDuration: "1m",
    },
  },
};

const questions = [
  "Preporuči knjigu",
  "Koje je radno vrijeme?",
  "Ima li Harry Potter?",
  "Koja su događanja?",
  "Kako se učlaniti?",
  "Tko je napisao Dinu?",
  "Preporuči krimić",
  "Što je novo u knjižnici?",
  "Ima li knjiga Atomic Habits?",
  "Koliko knjiga mogu posuditi?",
];

export default function () {
  const question = questions[__VU % questions.length];

  http.post(
    "http://localhost:8000/api/chat",
    JSON.stringify({
      message: question,
      history: [],
    }),
    {
      headers: {
        "Content-Type": "application/json",
      },
    },
  );
}
