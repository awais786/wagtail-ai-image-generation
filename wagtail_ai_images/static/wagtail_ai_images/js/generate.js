/**
 * generate.js — client-side logic for the AI image generation form.
 *
 * Responsibilities:
 *  - Intercept form submit and POST via fetch (no full-page reload)
 *  - Show a loading indicator while the request is in flight
 *  - On success: render the generated image preview and a library link
 *  - On error: display the server-provided message
 *
 * CSRF: the hidden csrfmiddlewaretoken field produced by {% csrf_token %} is
 * included automatically when FormData is constructed from the <form> element.
 * Django's CSRF middleware accepts it as a POST field, so no extra header work
 * is needed.
 */
(function () {
  "use strict";

  var form = document.getElementById("ai-generate-form");
  if (!form) return;

  var btn = document.getElementById("ai-generate-btn");
  var statusDiv = document.getElementById("ai-generate-status");
  var loadingDiv = document.getElementById("ai-generate-loading");
  var errorDiv = document.getElementById("ai-generate-error");
  var errorText = document.getElementById("ai-generate-error-text");
  var resultDiv = document.getElementById("ai-generate-result");
  var previewImg = document.getElementById("ai-generate-preview");
  var libraryLink = document.getElementById("ai-generate-library-link");

  function setLoading(active) {
    btn.disabled = active;
    if (active) {
      btn.classList.add("button-longrunning-active");
    } else {
      btn.classList.remove("button-longrunning-active");
    }
    statusDiv.style.display = "block";
    loadingDiv.style.display = active ? "block" : "none";
    errorDiv.style.display = "none";
    resultDiv.style.display = "none";
  }

  function showError(message) {
    errorText.textContent = message;
    errorDiv.style.display = "block";
    loadingDiv.style.display = "none";
    resultDiv.style.display = "none";
  }

  function showResult(data) {
    previewImg.src = data.image_url;
    previewImg.alt = data.image_title || "AI Generated Image";
    libraryLink.href = data.image_edit_url;
    resultDiv.style.display = "block";
    loadingDiv.style.display = "none";
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();

    var promptField = document.getElementById("id_prompt");
    if (!promptField || !promptField.value.trim()) {
      showError("Please enter a prompt.");
      statusDiv.style.display = "block";
      return;
    }

    setLoading(true);

    fetch(form.action || window.location.href, {
      method: "POST",
      body: new FormData(form),
      headers: {
        "X-Requested-With": "XMLHttpRequest",
      },
    })
      .then(function (response) {
        var contentType = response.headers.get("Content-Type") || "";
        if (contentType.indexOf("application/json") !== -1) {
          return response
            .json()
            .then(function (data) {
              return { ok: response.ok, status: response.status, data: data };
            })
            .catch(function () {
              return {
                ok: response.ok,
                status: response.status,
                data: { success: false, error: "The server returned an invalid response. Please try again." },
              };
            });
        }
        return response.text().then(function (text) {
          return {
            ok: response.ok,
            status: response.status,
            data: { success: false, error: text.trim().slice(0, 500) || "An unexpected error occurred. Please try again." },
          };
        });
      })
      .then(function (result) {
        setLoading(false);
        if (result.data && result.data.success) {
          showResult(result.data);
        } else {
          showError((result.data && result.data.error) || "An unexpected error occurred. Please try again.");
        }
      })
      .catch(function (err) {
        setLoading(false);
        showError("Network error: " + err.message);
      });
  });
})();
