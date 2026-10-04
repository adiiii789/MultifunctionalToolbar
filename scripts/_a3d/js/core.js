/* core.js - Gemeinsame Variablen (Szene, Kamera) und Chat
   Teil des 3D-Assistenten (siehe viewer.html für die Ladereihenfolge).
   Alle Dateien sind klassische Skripte und teilen sich den globalen Bereich. */

/* -------------------------
   Globals & Chat handling
   ------------------------- */
const MODE = (new URLSearchParams(location.search).get("mode") || "window").toLowerCase();
// Position und Größe des Chats setzt stage.js (Streifen unter dem Board)

let scene, camera, renderer, mixer, outlineEffect;
const morphMeshes = []; // alle Meshes mit MorphTargets

// Chat
const chatInput = document.getElementById("chat-input");
const chatMessages = document.getElementById("chat-messages");

chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && chatInput.value.trim() !== "") {
    const message = chatInput.value.trim();
    addMessage("Du", message);
    chatInput.value = "";
    speak(message);
  }
});

function addMessage(sender, text) {
  const messageElem = document.createElement("div");
  messageElem.style.marginBottom = "5px";
  const name = document.createElement("strong");
  name.textContent = sender + ": ";
  messageElem.append(name, document.createTextNode(text));   // kein HTML aus Nutzertext
  chatMessages.appendChild(messageElem);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}
