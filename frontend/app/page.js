"use client";
import { useState } from "react";
import axios from "axios";

export default function Home() {
  const [excelFile, setExcelFile] = useState(null);
  const [message, setMessage] = useState("");
  const [numbers, setNumbers] = useState([]);
  const [sending, setSending] = useState(false);
  const [status, setStatus] = useState([]);

  const uploadExcel = async () => {
    const formData = new FormData();
    formData.append("file", excelFile);

    const res = await axios.post(
      "http://127.0.0.1:8000/upload_excel/",
      formData,
      {
        headers: { "Content-Type": "multipart/form-data" },
      }
    );

    const rows = res.data.rows;
    const nums = rows.map((r) => r.phone);
    setNumbers(nums);
    alert("Excel uploaded successfully!");
  };

  const sendMessages = async () => {
    setSending(true);

    const res = await axios.post(
      "http://127.0.0.1:8000/send_bulk_message/",
      new URLSearchParams({
        message: message,
        numbers: numbers.join(","),
      })
    );

    setStatus(res.data.sent);
    setSending(false);
  };

  return (
    <div className="p-10 max-w-xl mx-auto">
      <h1 className="text-3xl font-bold mb-6">BoxBox WhatsApp Sender 🚀</h1>

      <div className="mb-6">
        <label className="font-semibold">Upload Excel File:</label>
        <input
          type="file"
          className="block mt-2"
          onChange={(e) => setExcelFile(e.target.files[0])}
        />
        <button
          className="bg-blue-600 text-white px-4 py-2 mt-3 rounded"
          onClick={uploadExcel}
        >
          Upload
        </button>
      </div>

      <div className="mb-6">
        <label className="font-semibold">Message:</label>
        <textarea
          className="w-full border p-3 mt-2 rounded"
          rows="4"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
        />
      </div>

      <button
        className="bg-green-600 text-white px-6 py-3 rounded"
        onClick={sendMessages}
        disabled={sending}
      >
        {sending ? "Sending..." : "Send Messages"}
      </button>

      {/* Status Section */}
      {status.length > 0 && (
        <div className="mt-10">
          <h2 className="text-xl font-semibold mb-3">Delivery Status</h2>
          {status.map((s, index) => (
            <div key={index} className="border p-3 my-2 rounded">
              Number: {s.number} — Status: {s.status}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
