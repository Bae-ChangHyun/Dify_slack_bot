import json

class ModalBuilder:
    def __init__(self):
        self.modal_configs = {
            "main_settings": {
                "type": "modal",
                "callback_id": "main_settings_modal",
                "title": {"type": "plain_text", "text": "Bot 설정"},
                "submit": {"type": "plain_text", "text": "저장"},
            },
            "prompt_edit": {
                "type": "modal",
                "callback_id": "prompt_edit_modal",
                "title": {"type": "plain_text", "text": "프롬프트 수정"},
                "submit": {"type": "plain_text", "text": "완료"},
            }
        }
    
    def create_select_config(self, current_model, available_models):
        select_config = {
            "type": "static_select",
            "placeholder": {"type": "plain_text", "text": "모델 선택"},
            "options": [
                {"text": {"type": "plain_text", "text": model}, "value": model}
                for model in available_models
            ],
            "action_id": "model_select"
        }
        
        if current_model in available_models:
            select_config["initial_option"] = {
                "text": {"type": "plain_text", "text": current_model},
                "value": current_model
            }
        return select_config
    
    def create_main_modal_blocks(self, current_model, current_prompt, available_models):
        return [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*AI 모델 설정*"},
                "accessory": self.create_select_config(current_model, available_models)
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*현재 프롬프트*\n{current_prompt}"},
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "프롬프트 수정"},
                    "action_id": "open_prompt_modal"
                }
            }
        ]
    
    def create_prompt_modal_blocks(self, current_prompt):
        return [{
            "type": "input",
            "block_id": "prompt_input_block",
            "element": {
                "type": "plain_text_input",
                "action_id": "prompt_input",
                "initial_value": current_prompt,
                "multiline": True
            },
            "label": {"type": "plain_text", "text": "프롬프트"}
        }]
    
    def get_modal_config(self, modal_type, blocks, metadata):
        config = self.modal_configs[modal_type].copy()
        config.update({
            "blocks": blocks,
            "private_metadata": json.dumps(metadata)
        })
        return config 