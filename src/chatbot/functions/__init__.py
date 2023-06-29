from functions import browser, helpers, restaurants

available_functions = {
    "search_restaurants": restaurants.search_restaurants,
    "get_current_time": helpers.get_current_time,
    "get_search_results": browser.fetch_search_result,
}

function_info = [
    {
        "name": "search_restaurants",
        "description": "ホットペッパーグルメで飲食店を検索する",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "店名、お店ジャンル等のフリーワード。半角スペース区切りの文字列を渡すことでAND検索になる (例)「焼肉」",
                },
                "address": {
                    "type": "string",
                    "description": "店のエリア、駅名など (例)「東京」「所沢駅」",
                },
                "is_point": {
                    "type": "boolean",
                    "description": "建物や駅などある地点の近くを検索する場合はtrue、エリア全体を検索する場合はfalse",
                },
            },
            "required": ["keyword", "address", "is_point"],
        },
    },
    # {
    #    "name": "get_current_time",
    #    "description": "現在の日時や曜日を取得する",
    #    "parameters": {
    #        "type": "object",
    #        "properties": {},
    #        "required": [],
    #    },
    # },
    {
        "name": "get_search_results",
        "description": "Googleで検索する",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Google検索に入力するクエリ",
                },
            },
            "required": ["query"],
        },
    },
]
