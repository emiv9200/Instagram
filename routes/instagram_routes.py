from flask import Blueprint, jsonify, request
from models.instagram_models import InstagramModel
from services.instagram_service import InstagramService
import logging

logger = logging.getLogger(__name__)

instagram_bp = Blueprint("instagram", __name__, url_prefix="/api/instagram")


@instagram_bp.route("/post/<int:post_id>", methods=["POST"])
def post_to_instagram(post_id):
    try:
        result = InstagramService.post_to_instagram(post_id)
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.exception("Instagram post endpoint hatası")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@instagram_bp.route("/stats", methods=["GET"])
def get_stats():
    try:
        stats = InstagramModel.get_stats()
        
        return jsonify({
            "success": True,
            "stats": stats
        })
        
    except Exception as e:
        logger.exception("Instagram stats hatası")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@instagram_bp.route("/unposted", methods=["GET"])
def get_unposted():
    try:
        limit = request.args.get('limit', 10, type=int)
        
        posts = InstagramModel.get_unposted_posts(limit=limit)
        
        return jsonify({
            "success": True,
            "count": len(posts),
            "posts": posts
        })
        
    except Exception as e:
        logger.exception("Instagram unposted hatası")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@instagram_bp.route("/create", methods=["POST"])
def create_post():
    try:
        data = request.json
        
        title = data.get('title')
        content = data.get('content')
        image_url = data.get('image_url')
        source_url = data.get('source_url')
        category = data.get('category', 'teknoloji')
        
        if not title or not content:
            return jsonify({
                "success": False,
                "error": "Title ve content gerekli"
            }), 400
        
        summary = InstagramService.generate_summary(title, content)
        
        if not summary:
            return jsonify({
                "success": False,
                "error": "Özet oluşturulamadı"
            }), 500
        
        post_data = {
            "title": title,
            "description": content,
            "summary": summary,
            "image_url": image_url,
            "source_url": source_url,
            "category": category
        }
        
        success = InstagramModel.save_post(post_data)
        
        if success:
            return jsonify({
                "success": True,
                "message": "Post oluşturuldu",
                "summary": summary
            })
        else:
            return jsonify({
                "success": False,
                "error": "Post kaydedilemedi (duplicate olabilir)"
            }), 400
            
    except Exception as e:
        logger.exception("Create post hatası")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
