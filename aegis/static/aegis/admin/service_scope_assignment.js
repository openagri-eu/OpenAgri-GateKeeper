(function () {
  function findRow(fieldName) {
    return document.querySelector(
      ".form-row.field-" + fieldName + ", .field-" + fieldName
    );
  }

  function findInput(fieldName) {
    return document.getElementById("id_" + fieldName);
  }

  function setRowVisibility(fieldName, visible) {
    var row = findRow(fieldName);
    var input = findInput(fieldName);
    if (!row) {
      return;
    }
    row.style.display = visible ? "" : "none";
    if (input) {
      input.disabled = !visible;
    }
  }

  function syncSubjectFields() {
    var subjectType = findInput("subject_type");
    if (!subjectType) {
      return;
    }
    var isGroup = subjectType.value === "group";
    setRowVisibility("subject_group", isGroup);
    setRowVisibility("subject_user", !isGroup);
  }

  function syncScopeFields() {
    var scopeType = findInput("scope_type");
    if (!scopeType) {
      return;
    }
    var isFarm = scopeType.value === "farm";
    var isParcel = scopeType.value === "parcel";
    setRowVisibility("scope_farm", isFarm);
    setRowVisibility("scope_parcel", isParcel);
  }

  function init() {
    var subjectType = findInput("subject_type");
    var scopeType = findInput("scope_type");

    syncSubjectFields();
    syncScopeFields();

    if (subjectType) {
      subjectType.addEventListener("change", syncSubjectFields);
    }
    if (scopeType) {
      scopeType.addEventListener("change", syncScopeFields);
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
