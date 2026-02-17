<<<<<<< HEAD
document.addEventListener("DOMContentLoaded", function () {

    const ctx = document.getElementById('confidenceChart');

    if (ctx) {
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: ["Round 1", "Round 2", "Round 3", "Round 4"],
                datasets: [{
                    label: "Model Confidence",
                    data: [65, 72, 80, 90],
                    borderColor: "red",
                    fill: false,
                    tension: 0.3
                }]
            },
            options: {
                responsive: true
            }
        });
    }

});
=======
document.addEventListener("DOMContentLoaded", function () {

    const ctx = document.getElementById('confidenceChart');

    if (ctx) {
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: ["Round 1", "Round 2", "Round 3", "Round 4"],
                datasets: [{
                    label: "Model Confidence",
                    data: [65, 72, 80, 90],
                    borderColor: "red",
                    fill: false,
                    tension: 0.3
                }]
            },
            options: {
                responsive: true
            }
        });
    }

});
>>>>>>> 6ed5a0610661de02d4c9fa8781a0f9e0d1287d6c
