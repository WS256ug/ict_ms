(function () {
    function getComputerInlineGroup() {
        var computerField = document.querySelector("[name$='-computer_type']");
        if (computerField) {
            return computerField.closest(".inline-group") || computerField.closest(".module");
        }

        return (
            document.getElementById("computer_details-group") ||
            document.getElementById("computerasset_set-group")
        );
    }

    function categorySupportsComputerDetails(categorySelect) {
        if (!categorySelect || categorySelect.selectedIndex < 0) {
            return false;
        }

        var label = categorySelect.options[categorySelect.selectedIndex].text.toLowerCase();
        return ["computer", "desktop", "laptop", "server", "workstation"].some(function (keyword) {
            return label.indexOf(keyword) !== -1;
        });
    }

    function hasExistingComputerDetails(group) {
        if (!group) {
            return false;
        }

        var idField = group.querySelector("input[name$='-id']");
        return Boolean(idField && idField.value);
    }

    function toggleComputerInline() {
        var categorySelect = document.getElementById("id_category");
        var group = getComputerInlineGroup();

        if (!categorySelect || !group) {
            return;
        }

        var showInline = categorySupportsComputerDetails(categorySelect) || hasExistingComputerDetails(group);
        group.style.display = showInline ? "" : "none";
    }

    document.addEventListener("DOMContentLoaded", function () {
        var categorySelect = document.getElementById("id_category");
        if (!categorySelect) {
            return;
        }

        toggleComputerInline();
        categorySelect.addEventListener("change", toggleComputerInline);
    });
})();
