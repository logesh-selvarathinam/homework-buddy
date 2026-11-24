// Reads a homework diary photo / school-app screenshot with Google Gemini
// and returns the homework as "Subject: task" lines for the app's parser.
// Only signed-in app users can call it (Supabase checks their login token).
//
// Secrets (set by the "Set up Supabase" GitHub workflow):
//   GEMINI_API_KEY  – from https://aistudio.google.com/apikey
//   GEMINI_MODEL    – optional, default gemini-2.5-flash

const PROMPT = `This image is a page of an Indian school homework diary (handwritten) or a screenshot
of a school app / WhatsApp message with today's homework.

Write out the homework only, one line per subject, exactly in this form:
Subject: task

Rules:
- Use these subject names when they fit: Maths, English, Tamil, Hindi, EVS, Social, Science, Computer, GK.
- Keep Tamil and Hindi words in their own script, as written.
- Keep page numbers, unit numbers, exercise numbers and "1 time" / "R/W" notes.
- Mention tests (slip test, A/B test, unit test) in the task text.
- Ignore printed labels of the diary page (Date boxes, Parent's sign, Bed time, Wake up time,
  smiley boxes, mottos) and teachers' ticks or signatures.
- If a word is unclear, give your best guess followed by (?).
- Output only the lines, nothing else. If there is no homework, output: NONE`;

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ error: "POST only" }, 405);

  const key = Deno.env.get("GEMINI_API_KEY");
  if (!key) return json({ error: "Photo reading is not set up: GEMINI_API_KEY is missing" }, 500);
  const model = Deno.env.get("GEMINI_MODEL") || "gemini-2.5-flash";

  let image = "", mime = "image/jpeg";
  try {
    const body = await req.json();
    image = String(body.image || "");
    mime = String(body.mime || mime);
  } catch {
    return json({ error: "Send JSON: {image: <base64>, mime}" }, 400);
  }
  if (!image) return json({ error: "No image" }, 400);
  if (image.length > 10_000_000) return json({ error: "Image too big" }, 413);

  const r = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-goog-api-key": key },
      body: JSON.stringify({
        contents: [{ parts: [{ text: PROMPT }, { inline_data: { mime_type: mime, data: image } }] }],
        generationConfig: { temperature: 0 },
      }),
    },
  );
  const j = await r.json().catch(() => ({}));
  if (!r.ok) {
    return json({ error: j?.error?.message || `Gemini error ${r.status}` }, 502);
  }
  const text = (j?.candidates?.[0]?.content?.parts ?? [])
    .map((p: { text?: string }) => p.text ?? "")
    .join("")
    .trim();
  return json({ text: text === "NONE" ? "" : text });
});
