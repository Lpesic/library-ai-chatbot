import http from "k6/http";

export const options = {
  scenarios: {
    chatbot: {
      executor: "per-vu-iterations",
      vus: 4,
      iterations: 1,
    },
  },
};

const questions = [
  "Koje je radno vrijeme?",
  "Kako se učlaniti?",
  "Koja su događanja?",
  "Koliko knjiga mogu posuditi?",
];

export default function () {
  const question = questions[__VU - 1];

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
