function renderLaunchTimeTable(content_length_report) {
    $('#launch-time tbody').empty();

    window.alternate = false;
    $('#launch-time tbody').jqoteapp($('#launch-time-template'), content_length_report.stats);
}

function updateLaunchTimeStats() {
    $.get('./launch-times', function (launch_time_report) {
        window.launch_time_report = launch_time_report;
        $('#launch-time tbody').empty();
        if (JSON.stringify(launch_time_report) !== JSON.stringify({})) {
            renderLaunchTimeTable(launch_time_report);
        };
        setTimeout(updateLaunchTimeStats, 2000);
    });
}

updateLaunchTimeStats();