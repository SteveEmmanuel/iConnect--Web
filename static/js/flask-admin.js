$(document).ready(function(){
    var ugly = $( "#details" ).val();
    ugly = ugly.replace(/'/g, '"');
    var obj = JSON.parse(ugly);
    var pretty = JSON.stringify(obj, undefined, 4);
    $( "#details" ).val(pretty)
});